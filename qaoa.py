"""
============================================================
Q-PORTFOLIO
Step 4 — STABLE QAOA ENGINE

Purpose:
    Convert a binary QUBO into an Ising Hamiltonian
    and solve it using QAOA with a local Qiskit Aer
    simulator.

Design goals:
    1. Preserve the existing QUBO mathematics.
    2. Preserve the existing frontend response format.
    3. Prevent overlapping QAOA simulations.
    4. Make repeated executions more stable.
    5. Control Aer CPU parallelism.
    6. Provide useful backend errors.
    7. Clean simulator resources after execution.

Frontend-compatible response fields:

    status
    algorithm
    depth
    qubits
    shots
    optimalParameters
    bestSolution
    topSolutions
    optimizer
============================================================
"""

from typing import List, Dict
import threading
import gc

import numpy as np
from scipy.optimize import minimize

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator


# ============================================================
# GLOBAL QAOA EXECUTION LOCK
# ============================================================
#
# FastAPI can execute synchronous endpoints in different
# worker threads.
#
# Without a lock, two browser requests can potentially run
# Aer simulations simultaneously.
#
# We deliberately serialize QAOA executions for stability.
#
# This does NOT change the QAOA mathematics.
# ============================================================

QAOA_EXECUTION_LOCK = threading.Lock()


class QAOASolver:

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(
        self,
        Q: List[List[float]],
        constant: float = 0.0,
        depth: int = 2,
        shots: int = 2048,
    ):

        # ----------------------------------------------------
        # Validate QUBO
        # ----------------------------------------------------

        self.Q = np.asarray(
            Q,
            dtype=float
        )

        if self.Q.ndim != 2:

            raise ValueError(
                "QUBO matrix must be two-dimensional."
            )

        if (
            self.Q.shape[0]
            != self.Q.shape[1]
        ):

            raise ValueError(
                "QUBO matrix must be square."
            )

        if self.Q.shape[0] == 0:

            raise ValueError(
                "QUBO matrix cannot be empty."
            )

        if not np.all(
            np.isfinite(self.Q)
        ):

            raise ValueError(
                "QUBO matrix contains NaN or infinite values."
            )


        self.constant = float(
            constant
        )

        if not np.isfinite(
            self.constant
        ):

            raise ValueError(
                "QUBO constant must be finite."
            )


        # ----------------------------------------------------
        # QAOA configuration
        # ----------------------------------------------------

        self.n = int(
            self.Q.shape[0]
        )

        self.depth = int(
            depth
        )

        self.shots = int(
            shots
        )


        if self.depth < 1:

            raise ValueError(
                "QAOA depth must be at least 1."
            )


        if self.shots < 1:

            raise ValueError(
                "QAOA shots must be at least 1."
            )


        # ----------------------------------------------------
        # Ising coefficients
        # ----------------------------------------------------

        self.h = np.zeros(
            self.n,
            dtype=float
        )

        self.J: Dict[
            tuple,
            float
        ] = {}


        self.ising_constant = float(
            self.constant
        )


        # ----------------------------------------------------
        # Create a fresh Aer simulator.
        #
        # Important:
        # We deliberately restrict parallelism.
        #
        # This makes repeated local Windows executions more
        # predictable and prevents Aer from aggressively
        # consuming CPU resources.
        # ----------------------------------------------------

        self.backend = AerSimulator(

            method="automatic",

            max_parallel_threads=1,

            max_parallel_experiments=1,

            seed_simulator=42
        )


        # ----------------------------------------------------
        # Convert QUBO → Ising
        # ----------------------------------------------------

        self._qubo_to_ising()


    # ========================================================
    # QUBO → ISING
    # ========================================================

    def _qubo_to_ising(self):

        """
        Mapping:

            x_i = (1 - Z_i) / 2

        QUBO:

            E(x) = x^T Q x + constant

        The PortfolioQUBO implementation stores pair
        coefficients in the upper triangle.

        Therefore:

            physical pair coefficient = 2 * Q[i,j]

        This preserves the existing mathematical convention.
        """

        # ----------------------------------------------------
        # Diagonal terms
        # ----------------------------------------------------

        for i in range(self.n):

            qii = float(
                self.Q[i, i]
            )


            self.ising_constant += (
                qii / 2.0
            )


            self.h[i] += (
                -qii / 2.0
            )


        # ----------------------------------------------------
        # Pairwise terms
        # ----------------------------------------------------

        for i in range(self.n):

            for j in range(
                i + 1,
                self.n
            ):

                qij = float(
                    self.Q[i, j]
                )


                if abs(qij) < 1e-12:

                    continue


                pair = (
                    2.0 * qij
                )


                self.ising_constant += (
                    pair / 4.0
                )


                self.h[i] += (
                    -pair / 4.0
                )


                self.h[j] += (
                    -pair / 4.0
                )


                self.J[
                    (i, j)
                ] = (
                    pair / 4.0
                )


        # ----------------------------------------------------
        # Numerical validation
        # ----------------------------------------------------

        if not np.all(
            np.isfinite(self.h)
        ):

            raise ValueError(
                "Invalid Ising linear coefficients."
            )


        if not np.isfinite(
            self.ising_constant
        ):

            raise ValueError(
                "Invalid Ising constant."
            )


    # ========================================================
    # QUBO ENERGY
    # ========================================================

    def qubo_energy(
        self,
        bitstring: str
    ) -> float:

        if len(bitstring) != self.n:

            raise ValueError(
                "Bitstring length must equal "
                f"{self.n}"
            )


        if any(
            bit not in "01"
            for bit in bitstring
        ):

            raise ValueError(
                "Bitstring must contain only 0 and 1."
            )


        x = np.array(
            [
                int(bit)
                for bit in bitstring
            ],
            dtype=float
        )


        energy = (
            x @ self.Q @ x
            + self.constant
        )


        if not np.isfinite(
            energy
        ):

            raise RuntimeError(
                "QUBO energy became NaN or infinite."
            )


        return float(
            energy
        )


    # ========================================================
    # QAOA CIRCUIT
    # ========================================================

    def build_circuit(
        self,
        gammas: np.ndarray,
        betas: np.ndarray,
    ) -> QuantumCircuit:

        # ----------------------------------------------------
        # Validate parameter sizes
        # ----------------------------------------------------

        if len(gammas) != self.depth:

            raise ValueError(
                "Gamma parameter count does not match QAOA depth."
            )


        if len(betas) != self.depth:

            raise ValueError(
                "Beta parameter count does not match QAOA depth."
            )


        qc = QuantumCircuit(
            self.n,
            self.n
        )


        # ----------------------------------------------------
        # Initial |+> state
        # ----------------------------------------------------

        for qubit in range(
            self.n
        ):

            qc.h(
                qubit
            )


        # ----------------------------------------------------
        # QAOA layers
        # ----------------------------------------------------

        for layer in range(
            self.depth
        ):

            gamma = float(
                gammas[layer]
            )

            beta = float(
                betas[layer]
            )


            if not np.isfinite(
                gamma
            ):

                raise ValueError(
                    "QAOA gamma parameter is not finite."
                )


            if not np.isfinite(
                beta
            ):

                raise ValueError(
                    "QAOA beta parameter is not finite."
                )


            # =================================================
            # COST HAMILTONIAN
            # =================================================

            # h_i Z_i

            for i in range(
                self.n
            ):

                angle = (
                    2.0
                    * gamma
                    * float(self.h[i])
                )


                if abs(angle) > 1e-12:

                    qc.rz(
                        angle,
                        i
                    )


            # =================================================
            # J_ij Z_i Z_j
            # =================================================

            for (
                i,
                j
            ), coupling in self.J.items():

                angle = (
                    2.0
                    * gamma
                    * float(coupling)
                )


                if abs(angle) <= 1e-12:

                    continue


                qc.cx(
                    i,
                    j
                )


                qc.rz(
                    angle,
                    j
                )


                qc.cx(
                    i,
                    j
                )


            # =================================================
            # MIXER
            # =================================================

            for i in range(
                self.n
            ):

                qc.rx(
                    2.0 * beta,
                    i
                )


        # ----------------------------------------------------
        # Measurement
        # ----------------------------------------------------

        qc.measure(
            range(self.n),
            range(self.n)
        )


        return qc


    # ========================================================
    # SAFE AER EXECUTION
    # ========================================================

    def _run_simulation(
        self,
        circuit: QuantumCircuit,
        shots: int,
    ):

        """
        Centralized Aer execution.

        Keeping all backend execution in one place gives us
        consistent error handling and makes repeated executions
        easier to diagnose.
        """

        if shots < 1:

            raise ValueError(
                "Simulation shots must be at least 1."
            )


        try:

            # ------------------------------------------------
            # Transpile for the current simulator.
            #
            # optimization_level=1 gives useful optimization
            # without spending excessive time compiling.
            # ------------------------------------------------

            compiled = transpile(
                circuit,
                self.backend,
                optimization_level=1
            )


            # ------------------------------------------------
            # Execute
            # ------------------------------------------------

            simulation = self.backend.run(
                compiled,
                shots=int(shots)
            )


            result = simulation.result()


            counts = result.get_counts()


        except Exception as exc:

            raise RuntimeError(
                "QAOA Aer simulation failed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc


        if not counts:

            raise RuntimeError(
                "QAOA Aer simulation returned no measurement results."
            )


        return counts


    # ========================================================
    # EXPECTATION VALUE
    # ========================================================

    def expectation(
        self,
        parameters: np.ndarray
    ) -> float:

        parameters = np.asarray(
            parameters,
            dtype=float
        )


        expected_size = (
            2 * self.depth
        )


        if parameters.size != (
            expected_size
        ):

            raise ValueError(
                "QAOA parameter vector must contain "
                f"{expected_size} values."
            )


        if not np.all(
            np.isfinite(parameters)
        ):

            raise ValueError(
                "QAOA parameter vector contains NaN or infinite values."
            )


        gammas = parameters[
            :self.depth
        ]


        betas = parameters[
            self.depth:
        ]


        # ----------------------------------------------------
        # Build circuit
        # ----------------------------------------------------

        circuit = self.build_circuit(
            gammas,
            betas
        )


        # ----------------------------------------------------
        # Run simulator
        # ----------------------------------------------------

        counts = self._run_simulation(
            circuit,
            self.shots
        )


        # ----------------------------------------------------
        # Calculate expectation value
        # ----------------------------------------------------

        total_energy = 0.0

        total_shots = sum(
            counts.values()
        )


        if total_shots <= 0:

            raise RuntimeError(
                "QAOA produced zero measurement shots."
            )


        for measured, count in counts.items():

            # Qiskit classical-bit order is reversed.

            bitstring = (
                measured[::-1]
            )


            # Defensive validation.

            if len(bitstring) != self.n:

                raise RuntimeError(
                    "QAOA returned an invalid bitstring length."
                )


            energy = self.qubo_energy(
                bitstring
            )


            total_energy += (
                float(energy)
                * int(count)
            )


        expectation_value = (
            total_energy
            / total_shots
        )


        if not np.isfinite(
            expectation_value
        ):

            raise RuntimeError(
                "QAOA expectation value became NaN or infinite."
            )


        return float(
            expectation_value
        )


    # ========================================================
    # OPTIMIZATION
    # ========================================================

    def optimize(self):

        """
        Run QAOA parameter optimization.

        The complete execution is protected by a global lock
        so simultaneous browser requests cannot make multiple
        Aer simulations compete for local resources.
        """

        # ====================================================
        # SERIALIZE QAOA EXECUTIONS
        # ====================================================

        acquired = (
            QAOA_EXECUTION_LOCK.acquire(
                timeout=180
            )
        )


        if not acquired:

            raise RuntimeError(
                "QAOA engine is busy with another optimization. "
                "Please try again shortly."
            )


        try:

            return self._optimize_locked()


        finally:

            # ------------------------------------------------
            # Always release the lock.
            # ------------------------------------------------

            QAOA_EXECUTION_LOCK.release()

            # ------------------------------------------------
            # Encourage Python to release temporary objects.
            # ------------------------------------------------

            gc.collect()


    # ========================================================
    # INTERNAL OPTIMIZATION
    # ========================================================

    def _optimize_locked(self):

        # ----------------------------------------------------
        # Deterministic initial parameters
        # ----------------------------------------------------

        rng = np.random.default_rng(
            42
        )


        initial = rng.uniform(
            0.0,
            np.pi,
            2 * self.depth
        )


        # ----------------------------------------------------
        # Validate initial parameters
        # ----------------------------------------------------

        if not np.all(
            np.isfinite(initial)
        ):

            raise RuntimeError(
                "Initial QAOA parameters are invalid."
            )


        # ====================================================
        # CLASSICAL PARAMETER OPTIMIZATION
        # ====================================================

        try:

            result = minimize(

                self.expectation,

                initial,

                method="COBYLA",

                options={
                    "maxiter": 60
                }
            )


        except Exception as exc:

            raise RuntimeError(
                "QAOA parameter optimization failed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc


        # ----------------------------------------------------
        # Validate optimizer result
        # ----------------------------------------------------

        if result.x is None:

            raise RuntimeError(
                "QAOA optimizer returned no parameters."
            )


        parameters = np.asarray(
            result.x,
            dtype=float
        )


        if parameters.size != (
            2 * self.depth
        ):

            raise RuntimeError(
                "QAOA optimizer returned an invalid parameter vector."
            )


        if not np.all(
            np.isfinite(parameters)
        ):

            raise RuntimeError(
                "QAOA optimizer returned NaN or infinite parameters."
            )


        # ----------------------------------------------------
        # Do not silently hide optimizer failure.
        #
        # COBYLA can return useful parameters even when its
        # convergence flag is false, so we keep the result
        # but expose the status in the frontend response.
        # ----------------------------------------------------


        gammas = parameters[
            :self.depth
        ]


        betas = parameters[
            self.depth:
        ]


        # ====================================================
        # FINAL OPTIMIZED CIRCUIT
        # ====================================================

        circuit = self.build_circuit(
            gammas,
            betas
        )


        # ====================================================
        # FINAL MEASUREMENT
        # ====================================================

        counts = self._run_simulation(
            circuit,
            self.shots
        )


        # ====================================================
        # RANK MEASURED STATES
        # ====================================================

        states = []


        total_shots = sum(
            counts.values()
        )


        if total_shots <= 0:

            raise RuntimeError(
                "QAOA produced no valid final measurement shots."
            )


        for measured, count in counts.items():

            bitstring = str(
                measured[::-1]
            )


            if len(bitstring) != self.n:

                raise RuntimeError(
                    "QAOA produced an invalid final bitstring."
                )


            energy = self.qubo_energy(
                bitstring
            )


            count = int(
                count
            )


            states.append({

                "bitstring":
                    bitstring,

                "energy":
                    float(energy),

                "shots":
                    count,

                "probability":
                    float(
                        count /
                        total_shots
                    )

            })


        # ----------------------------------------------------
        # Lowest QUBO energy first
        # ----------------------------------------------------

        states.sort(
            key=lambda item:
                item["energy"]
        )


        if not states:

            raise RuntimeError(
                "QAOA produced no measurement results."
            )


        best = states[0]


        # ====================================================
        # FINAL RESPONSE
        # ====================================================
        #
        # IMPORTANT:
        #
        # This structure intentionally matches your existing
        # frontend app.js.
        #
        # Do not rename these fields unless the frontend is
        # changed at the same time.
        # ====================================================

        return {

            "status":
                "success",

            "algorithm":
                "QAOA",

            "depth":
                int(self.depth),

            "qubits":
                int(self.n),

            "shots":
                int(self.shots),

            "optimalParameters": {

                "gamma": [
                    float(x)
                    for x in gammas
                ],

                "beta": [
                    float(x)
                    for x in betas
                ]

            },

            "bestSolution":
                best,

            "topSolutions":
                states[:10],

            "optimizer": {

                "method":
                    "COBYLA",

                "iterations":
                    int(
                        getattr(
                            result,
                            "nfev",
                            0
                        )
                    ),

                "converged":
                    bool(
                        getattr(
                            result,
                            "success",
                            False
                        )
                    )

            }

        }
