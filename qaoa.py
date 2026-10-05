"""
Q-PORTFOLIO
Step 4 — QAOA Engine

Converts a binary QUBO into an Ising Hamiltonian
and runs QAOA using a local Qiskit Aer simulator.
"""

from typing import List, Dict

import numpy as np
from scipy.optimize import minimize

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator


class QAOASolver:

    def __init__(
        self,
        Q: List[List[float]],
        constant: float = 0.0,
        depth: int = 2,
        shots: int = 2048,
    ):

        self.Q = np.asarray(Q, dtype=float)
        self.constant = float(constant)

        self.n = self.Q.shape[0]
        self.depth = int(depth)
        self.shots = int(shots)

        self.backend = AerSimulator()

        self.h = np.zeros(self.n, dtype=float)
        self.J: Dict[tuple, float] = {}

        self.ising_constant = float(self.constant)

        self._qubo_to_ising()


    # ==========================================================
    # QUBO → ISING
    # ==========================================================

    def _qubo_to_ising(self):

        """
        Mapping:

            x_i = (1 - Z_i) / 2

        The QUBO used by PortfolioQUBO is evaluated as:

            E(x) = x^T Q x + constant

        Since the QUBO stores pair coefficients in the
        upper triangle, the physical pair contribution is:

            2 * Q[i,j] * x_i * x_j
        """

        # ------------------------------------------------------
        # Diagonal terms
        # ------------------------------------------------------

        for i in range(self.n):

            qii = float(self.Q[i, i])

            self.ising_constant += qii / 2.0

            self.h[i] += -qii / 2.0


        # ------------------------------------------------------
        # Pairwise terms
        # ------------------------------------------------------

        for i in range(self.n):

            for j in range(i + 1, self.n):

                qij = float(self.Q[i, j])

                if abs(qij) < 1e-12:
                    continue

                # Because x^T Q x contains both Qij xi xj
                # and Qji xj xi, the effective coefficient
                # is 2*qij.

                pair = 2.0 * qij

                self.ising_constant += pair / 4.0

                self.h[i] += -pair / 4.0

                self.h[j] += -pair / 4.0

                self.J[(i, j)] = pair / 4.0


    # ==========================================================
    # QUBO ENERGY
    # ==========================================================

    def qubo_energy(
        self,
        bitstring: str
    ) -> float:

        if len(bitstring) != self.n:

            raise ValueError(
                "Bitstring length must equal "
                f"{self.n}"
            )

        x = np.array(
            [int(bit) for bit in bitstring],
            dtype=float
        )

        energy = (
            x @ self.Q @ x
            + self.constant
        )

        return float(energy)


    # ==========================================================
    # QAOA CIRCUIT
    # ==========================================================

    def build_circuit(
        self,
        gammas: np.ndarray,
        betas: np.ndarray,
    ) -> QuantumCircuit:

        qc = QuantumCircuit(
            self.n,
            self.n
        )


        # ------------------------------------------------------
        # Initial |+> state
        # ------------------------------------------------------

        for qubit in range(self.n):

            qc.h(qubit)


        # ------------------------------------------------------
        # QAOA layers
        # ------------------------------------------------------

        for layer in range(self.depth):

            gamma = float(gammas[layer])
            beta = float(betas[layer])


            # ==================================================
            # COST HAMILTONIAN
            # ==================================================

            # h_i Z_i

            for i in range(self.n):

                angle = 2.0 * gamma * float(self.h[i])

                if abs(angle) > 1e-12:

                    qc.rz(
                        angle,
                        i
                    )


            # J_ij Z_i Z_j

            for (i, j), coupling in self.J.items():

                angle = (
                    2.0 *
                    gamma *
                    float(coupling)
                )

                if abs(angle) <= 1e-12:
                    continue

                qc.cx(i, j)

                qc.rz(
                    angle,
                    j
                )

                qc.cx(i, j)


            # ==================================================
            # MIXER
            # ==================================================

            for i in range(self.n):

                qc.rx(
                    2.0 * beta,
                    i
                )


        # ------------------------------------------------------
        # Measurement
        # ------------------------------------------------------

        qc.measure(
            range(self.n),
            range(self.n)
        )

        return qc


    # ==========================================================
    # EXPECTATION VALUE
    # ==========================================================

    def expectation(
        self,
        parameters: np.ndarray
    ) -> float:

        gammas = parameters[
            :self.depth
        ]

        betas = parameters[
            self.depth:
        ]


        circuit = self.build_circuit(
            gammas,
            betas
        )


        compiled = transpile(
            circuit,
            self.backend
        )


        result = self.backend.run(
            compiled,
            shots=self.shots
        ).result()


        counts = result.get_counts()

        total_energy = 0.0

        total_shots = sum(
            counts.values()
        )


        for measured, count in counts.items():

            # Qiskit displays classical bits
            # in reverse order.

            bitstring = measured[::-1]

            energy = self.qubo_energy(
                bitstring
            )

            total_energy += (
                float(energy) *
                int(count)
            )


        return float(
            total_energy /
            total_shots
        )


    # ==========================================================
    # OPTIMIZATION
    # ==========================================================

    def optimize(self):

        rng = np.random.default_rng(
            42
        )


        initial = rng.uniform(
            0.0,
            np.pi,
            2 * self.depth
        )


        result = minimize(
            self.expectation,
            initial,
            method="COBYLA",
            options={
                "maxiter": 60
            }
        )


        parameters = np.asarray(
            result.x,
            dtype=float
        )


        gammas = parameters[
            :self.depth
        ]

        betas = parameters[
            self.depth:
        ]


        # ------------------------------------------------------
        # Final optimized circuit
        # ------------------------------------------------------

        circuit = self.build_circuit(
            gammas,
            betas
        )


        compiled = transpile(
            circuit,
            self.backend
        )


        simulation = self.backend.run(
            compiled,
            shots=self.shots
        ).result()


        counts = simulation.get_counts()


        # ======================================================
        # RANK MEASURED STATES
        # ======================================================

        states = []


        for measured, count in counts.items():

            bitstring = str(
                measured[::-1]
            )


            energy = self.qubo_energy(
                bitstring
            )


            count = int(count)


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
                        self.shots
                    )

            })


        # ------------------------------------------------------
        # Lowest QUBO energy first
        # ------------------------------------------------------

        states.sort(
            key=lambda item:
            item["energy"]
        )


        if not states:

            raise RuntimeError(
                "QAOA produced no measurement results."
            )


        best = states[0]


        # ======================================================
        # FINAL RESPONSE
        # ======================================================

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
                    int(result.nfev),

                "converged":
                    bool(result.success)

            }

        }