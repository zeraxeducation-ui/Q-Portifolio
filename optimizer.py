"""
Q-PORTFOLIO
Step 3 — QUBO Construction Engine

Decision variable:

    x_i ∈ {0, 1}

x_i = 1  -> asset selected
x_i = 0  -> asset not selected

The optimizer constructs:

    Q(x) = objective + constraint penalties

The resulting binary quadratic model can later be
converted into an Ising Hamiltonian for QAOA.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class Asset:
    id: str
    sector: str
    expected_return: float
    volatility: float


class PortfolioQUBO:

    def __init__(
        self,
        assets: List[Asset],
        portfolio_size: int,
        risk_tolerance: str = "balanced",
        sector_limit: int = 2,
    ):

        self.assets = assets

        self.n = len(assets)

        self.k = portfolio_size

        self.risk_tolerance = risk_tolerance

        self.sector_limit = sector_limit

        # QUBO matrix
        self.Q = np.zeros(
            (self.n, self.n),
            dtype=float
        )

        # Constant energy offset
        self.constant = 0.0

        self._build_model()


    # ==========================================================
    # RISK WEIGHT
    # ==========================================================

    def risk_weight(self):

        weights = {

            "conservative": 2.0,

            "balanced": 1.0,

            "aggressive": 0.45

        }

        return weights.get(
            self.risk_tolerance,
            1.0
        )


    # ==========================================================
    # OBJECTIVE
    # ==========================================================

    def _add_return_objective(self):

        """
        We minimize the QUBO.

        Therefore:

            high return -> negative energy

        Q_i_i += -return_i
        """

        for i, asset in enumerate(self.assets):

            self.Q[i, i] += (
                -asset.expected_return
            )


    # ==========================================================
    # INDIVIDUAL RISK
    # ==========================================================

    def _add_risk_objective(self):

        """
        Basic diagonal volatility penalty.

        Later we will upgrade this to a covariance matrix:

            x^T Σ x

        which introduces genuine pairwise portfolio risk.
        """

        weight = self.risk_weight()

        for i, asset in enumerate(self.assets):

            self.Q[i, i] += (
                weight *
                asset.volatility ** 2
            )


    # ==========================================================
    # CARDINALITY CONSTRAINT
    # ==========================================================

    def _add_cardinality_constraint(
        self,
        penalty: float = 10.0
    ):

        """
        Enforce:

            Σ x_i = K

        Penalty:

            A(Σx_i - K)^2

        Expanding:

            A[
                Σx_i
                +
                2Σ_{i<j}x_i x_j
                -
                2KΣx_i
                +
                K²
            ]

        Because x_i² = x_i for binary variables.
        """

        K = self.k
        A = penalty

        # Linear component
        for i in range(self.n):

            self.Q[i, i] += (
                A * (1 - 2 * K)
            )

        # Pairwise component
        for i in range(self.n):

            for j in range(i + 1, self.n):

                self.Q[i, j] += (
                    2 * A
                )

        # Constant
        self.constant += (
            A * K * K
        )


    # ==========================================================
    # SECTOR CONSTRAINT
    # ==========================================================

    def _add_sector_constraints(
        self,
        penalty: float = 8.0
    ):

        """
        For every sector:

            Σ x_i(sector) <= sector_limit

        We use a quadratic penalty when the selected
        count exceeds the allowed concentration.

        For a small hackathon problem, this is implemented
        through pairwise penalty terms.

        If more than L assets from the same sector are
        selected, combinations become increasingly expensive.
        """

        A = penalty

        sectors: Dict[str, List[int]] = {}

        for index, asset in enumerate(self.assets):

            sectors.setdefault(
                asset.sector,
                []
            ).append(index)


        for sector, indices in sectors.items():

            # If limit is 1, every pair from the same
            # sector should be penalized.

            if self.sector_limit == 1:

                for a in range(len(indices)):

                    for b in range(a + 1, len(indices)):

                        i = indices[a]
                        j = indices[b]

                        self.Q[i, j] += A

            else:

                # For L=2, penalize triples using
                # cubic logic approximately through
                # pairwise concentration pressure.

                pair_penalty = (
                    A /
                    max(self.sector_limit, 1)
                )

                for a in range(len(indices)):

                    for b in range(a + 1, len(indices)):

                        i = indices[a]
                        j = indices[b]

                        self.Q[i, j] += pair_penalty


    # ==========================================================
    # BUILD
    # ==========================================================

    def _build_model(self):

        self._add_return_objective()

        self._add_risk_objective()

        self._add_cardinality_constraint()

        self._add_sector_constraints()


    # ==========================================================
    # ENERGY
    # ==========================================================

    def energy(
        self,
        bitstring: str
    ) -> float:

        """
        Evaluate:

            E(x) = x^T Q x + constant

        """

        if len(bitstring) != self.n:

            raise ValueError(
                "Bitstring length must equal "
                f"{self.n}"
            )

        x = np.array(
            [
                int(bit)
                for bit in bitstring
            ],
            dtype=float
        )

        return float(
            x @ self.Q @ x
            + self.constant
        )


    # ==========================================================
    # BRUTE FORCE BASELINE
    # ==========================================================

    def solve_exact(self) -> Tuple[str, float]:

        """
        Exact enumeration.

        IMPORTANT:

        This is NOT QAOA.

        It is our classical ground-truth benchmark.

        For 8 assets:

            2^8 = 256 states

        which is trivial to enumerate.

        Later we'll compare QAOA against this result.
        """

        best_bitstring = None

        best_energy = float("inf")

        for number in range(
            2 ** self.n
        ):

            bitstring = format(
                number,
                f"0{self.n}b"
            )

            energy = self.energy(
                bitstring
            )

            if energy < best_energy:

                best_energy = energy

                best_bitstring = bitstring

        return (
            best_bitstring,
            best_energy
        )


    # ==========================================================
    # EXPORT
    # ==========================================================

    def export(self):

        return {

            "num_variables": self.n,

            "constant": self.constant,

            "matrix": self.Q.tolist(),

            "risk_tolerance":
                self.risk_tolerance,

            "portfolio_size":
                self.k,

            "sector_limit":
                self.sector_limit,

        }