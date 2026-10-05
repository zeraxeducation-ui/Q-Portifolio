"""
Q-PORTFOLIO API

FastAPI backend for:
1. QUBO construction
2. Classical exact benchmark
3. QAOA optimization
"""

from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from optimizer import Asset, PortfolioQUBO
from qaoa import QAOASolver


app = FastAPI(
    title="Q-Portfolio Quantum Optimization API",
    version="0.2.0"
)


# Allow the frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# REQUEST MODELS
# ==========================================================

class AssetRequest(BaseModel):
    id: str
    sector: str
    expectedReturn: float
    volatility: float


class OptimizationRequest(BaseModel):
    capital: float
    numberOfAssets: int
    maxAllocation: float
    sectorLimit: int
    riskTolerance: str
    assets: List[AssetRequest]


# ==========================================================
# HEALTH CHECK
# ==========================================================

@app.get("/")
def root():

    return {
        "project": "Q-Portfolio",
        "status": "online",
        "engine": "QUBO + QAOA",
        "version": "0.2.0"
    }


# ==========================================================
# HELPER
# ==========================================================

def build_portfolio_model(
    request: OptimizationRequest
):

    assets = [

        Asset(
            id=asset.id,
            sector=asset.sector,
            expected_return=asset.expectedReturn,
            volatility=asset.volatility
        )

        for asset in request.assets
    ]


    model = PortfolioQUBO(

        assets=assets,

        portfolio_size=
            request.numberOfAssets,

        risk_tolerance=
            request.riskTolerance,

        sector_limit=
            request.sectorLimit
    )


    return assets, model


# ==========================================================
# QUBO ENDPOINT
# ==========================================================

@app.post("/qubo")
def create_qubo(
    request: OptimizationRequest
):

    assets, model = build_portfolio_model(
        request
    )


    best_bitstring, best_energy = (
        model.solve_exact()
    )


    selected_assets = [

        assets[i].id

        for i in range(len(assets))

        if best_bitstring[i] == "1"
    ]


    return {

        "status": "success",

        "qubo": model.export(),

        "classicalBenchmark": {

            "bitstring":
                best_bitstring,

            "energy":
                best_energy,

            "selectedAssets":
                selected_assets
        }
    }


# ==========================================================
# QAOA ENDPOINT
# ==========================================================

@app.post("/qaoa")
def run_qaoa(
    request: OptimizationRequest
):

    assets, model = build_portfolio_model(
        request
    )


    # ------------------------------------------------------
    # Create QAOA solver from the EXACT QUBO
    # ------------------------------------------------------

    solver = QAOASolver(

        Q=model.Q.tolist(),

        constant=model.constant,

        depth=2,

        shots=2048
    )


    # ------------------------------------------------------
    # Run QAOA
    # ------------------------------------------------------

    result = solver.optimize()


    # ------------------------------------------------------
    # Get quantum solution
    # ------------------------------------------------------

    quantum_bitstring = (
        result["bestSolution"]["bitstring"]
    )


    quantum_energy = (
        result["bestSolution"]["energy"]
    )


    selected_assets = [

        assets[i].id

        for i in range(len(assets))

        if quantum_bitstring[i] == "1"
    ]


    result["bestSolution"][
        "selectedAssets"
    ] = selected_assets


    # ------------------------------------------------------
    # Classical ground-truth benchmark
    # ------------------------------------------------------

    classical_bitstring, classical_energy = (
        model.solve_exact()
    )


    classical_assets = [

        assets[i].id

        for i in range(len(assets))

        if classical_bitstring[i] == "1"
    ]


    result["classicalBenchmark"] = {

        "bitstring":
            classical_bitstring,

        "energy":
            classical_energy,

        "selectedAssets":
            classical_assets
    }


    # ------------------------------------------------------
    # Compare QAOA with exact classical solution
    # ------------------------------------------------------

    result["comparison"] = {

        "quantumEnergy":
            quantum_energy,

        "classicalEnergy":
            classical_energy,

        "energyDifference":
            quantum_energy -
            classical_energy,

        "matchesClassical":
            quantum_bitstring ==
            classical_bitstring
    }


    return result