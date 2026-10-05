"use strict";

/*
============================================================
Q-PORTFOLIO
FRONTEND OPTIMIZATION ENGINE

Frontend:
1. Portfolio configuration
2. 8-asset universe
3. Portfolio constraints
4. FastAPI communication
5. Real QAOA result
6. Final portfolio display

Backend:
http://127.0.0.1:8000/qaoa
============================================================
*/


/* ============================================================
   API CONFIGURATION
   ============================================================ */

const API_BASE_URL = "http://127.0.0.1:8000";


/* ============================================================
   ASSET UNIVERSE
   ============================================================ */

const ASSETS = [

    {
        id: "TCS",
        name: "Tata Consultancy Services",
        sector: "Technology",
        expectedReturn: 0.142,
        volatility: 0.182
    },

    {
        id: "INFY",
        name: "Infosys",
        sector: "Technology",
        expectedReturn: 0.131,
        volatility: 0.176
    },

    {
        id: "RELIANCE",
        name: "Reliance Industries",
        sector: "Energy",
        expectedReturn: 0.158,
        volatility: 0.221
    },

    {
        id: "HDFCBANK",
        name: "HDFC Bank",
        sector: "Financials",
        expectedReturn: 0.124,
        volatility: 0.151
    },

    {
        id: "ICICIBANK",
        name: "ICICI Bank",
        sector: "Financials",
        expectedReturn: 0.139,
        volatility: 0.169
    },

    {
        id: "SUNPHARMA",
        name: "Sun Pharmaceutical",
        sector: "Healthcare",
        expectedReturn: 0.117,
        volatility: 0.163
    },

    {
        id: "HINDUNILVR",
        name: "Hindustan Unilever",
        sector: "Consumer",
        expectedReturn: 0.103,
        volatility: 0.137
    },

    {
        id: "LT",
        name: "Larsen & Toubro",
        sector: "Industrials",
        expectedReturn: 0.149,
        volatility: 0.205
    }

];


/* ============================================================
   APPLICATION STATE
   ============================================================ */

const state = {

    capital: 1000000,

    maxAssets: 4,

    maxAllocation: 40,

    sectorLimit: 2,

    riskTolerance: "balanced",

    selectedAssets: new Set()

};


/* ============================================================
   DOM REFERENCES
   ============================================================ */

const elements = {

    capitalSlider:
        document.getElementById("capitalSlider"),

    capitalDisplay:
        document.getElementById("capitalDisplay"),

    assetCountSlider:
        document.getElementById("assetCountSlider"),

    assetCountDisplay:
        document.getElementById("assetCountDisplay"),

    allocationSlider:
        document.getElementById("allocationSlider"),

    allocationDisplay:
        document.getElementById("allocationDisplay"),

    sectorSlider:
        document.getElementById("sectorSlider"),

    sectorDisplay:
        document.getElementById("sectorDisplay"),

    riskDisplay:
        document.getElementById("riskDisplay"),

    assetGrid:
        document.getElementById("assetGrid"),

    selectedCount:
        document.getElementById("selectedCount"),

    requiredCount:
        document.getElementById("requiredCount"),

    selectionWarning:
        document.getElementById("selectionWarning"),

    optimizeButton:
        document.getElementById("optimizeButton"),

    modelState:
        document.getElementById("modelState"),

    metricVariables:
        document.getElementById("metricVariables"),

    metricCapital:
        document.getElementById("metricCapital"),

    metricAllocation:
        document.getElementById("metricAllocation"),

    metricSector:
        document.getElementById("metricSector"),

    modelPreview:
        document.getElementById("modelPreview")

};


/* ============================================================
   DOM SAFETY CHECK
   ============================================================ */

function checkRequiredElements() {

    const required = [

        "assetGrid",
        "selectedCount",
        "requiredCount",
        "selectionWarning",
        "optimizeButton",
        "modelState",
        "modelPreview"

    ];

    const missing = required.filter(
        id => !elements[id]
    );

    if (missing.length > 0) {

        console.error(
            "Q-PORTFOLIO missing HTML elements:",
            missing
        );

        return false;

    }

    return true;

}


/* ============================================================
   FORMATTERS
   ============================================================ */

function formatCurrency(value) {

    return new Intl.NumberFormat(
        "en-IN",
        {
            style: "currency",
            currency: "INR",
            maximumFractionDigits: 0
        }
    ).format(value);

}


function formatPercent(value) {

    return `${(value * 100).toFixed(1)}%`;

}


/* ============================================================
   RENDER ASSET UNIVERSE
   ============================================================ */

function renderAssets() {

    if (!elements.assetGrid) {
        return;
    }

    elements.assetGrid.innerHTML = "";

    ASSETS.forEach(asset => {

        const card =
            document.createElement("article");

        card.className = "asset-card";

        card.dataset.asset =
            asset.id;

        if (
            state.selectedAssets.has(
                asset.id
            )
        ) {

            card.classList.add(
                "selected"
            );

        }

        card.innerHTML = `

            <div class="asset-symbol">
                ${asset.id}
            </div>

            <div class="asset-name">
                ${asset.name}
            </div>

            <div class="asset-meta">

                <span class="asset-return">
                    RETURN ${formatPercent(asset.expectedReturn)}
                </span>

                <span class="asset-risk">
                    σ ${formatPercent(asset.volatility)}
                </span>

            </div>

            <div class="asset-sector">
                ${asset.sector.toUpperCase()}
            </div>

        `;

        card.addEventListener(
            "click",
            () => {

                toggleAsset(
                    asset.id
                );

            }
        );

        elements.assetGrid.appendChild(
            card
        );

    });

}


/* ============================================================
   ASSET SELECTION
   ============================================================ */

function toggleAsset(assetId) {

    const isSelected =
        state.selectedAssets.has(
            assetId
        );


    if (isSelected) {

        state.selectedAssets.delete(
            assetId
        );

    } else {

        if (
            state.selectedAssets.size >=
            state.maxAssets
        ) {

            showMessage(
                `Portfolio size limited to ${state.maxAssets} assets.`
            );

            return;

        }

        state.selectedAssets.add(
            assetId
        );

    }


    updateInterface();

}


/* ============================================================
   VALIDATE SELECTION
   ============================================================ */

function validateSelection() {

    const selectedIds =
        [...state.selectedAssets];


    const selectedAssets =
        ASSETS.filter(
            asset =>
                selectedIds.includes(
                    asset.id
                )
        );


    const exactlyK =
        selectedAssets.length ===
        state.maxAssets;


    const sectorCounts = {};


    selectedAssets.forEach(
        asset => {

            sectorCounts[
                asset.sector
            ] =
                (
                    sectorCounts[
                        asset.sector
                    ] || 0
                ) + 1;

        }
    );


    const violatingSectors =
        Object.entries(
            sectorCounts
        ).filter(
            ([, count]) =>
                count >
                state.sectorLimit
        );


    const sectorValid =
        violatingSectors.length === 0;


    return {

        valid:
            exactlyK &&
            sectorValid,

        exactlyK,

        sectorValid,

        sectorCounts,

        violatingSectors

    };

}


/* ============================================================
   BUILD OPTIMIZATION MODEL
   ============================================================ */

function buildOptimizationModel() {

    const validation =
        validateSelection();


    return {

        problem:
            "constrained_portfolio_selection",

        solver:
            "QAOA",

        capital:
            state.capital,

        numberOfAssets:
            state.maxAssets,

        maxAllocation:
            state.maxAllocation / 100,

        sectorLimit:
            state.sectorLimit,

        riskTolerance:
            state.riskTolerance,

        assets:
            ASSETS.map(
                (asset, index) => ({

                    index,

                    id:
                        asset.id,

                    sector:
                        asset.sector,

                    expectedReturn:
                        asset.expectedReturn,

                    volatility:
                        asset.volatility,

                    decisionVariable:
                        `x_${index}`,

                    selected:
                        state.selectedAssets.has(
                            asset.id
                        )

                })
            ),

        constraints: {

            cardinality: {

                type:
                    "equality",

                expression:
                    `Σ x_i = ${state.maxAssets}`

            },

            singleAssetAllocation: {

                type:
                    "upper_bound",

                expression:
                    `w_i ≤ ${state.maxAllocation}`

            },

            sectorConcentration: {

                type:
                    "upper_bound",

                expression:
                    `Σ x_i(sector) ≤ ${state.sectorLimit}`

            }

        },

        validation

    };

}


/* ============================================================
   MODEL PREVIEW
   ============================================================ */

function updateModelPreview() {

    if (!elements.modelPreview) {
        return;
    }


    const model =
        buildOptimizationModel();


    const selected =
        model.assets
            .filter(
                asset =>
                    asset.selected
            )
            .map(
                asset =>
                    asset.id
            );


    const selectedText =
        selected.length
            ? selected.join(", ")
            : "none";


    /*
       Only show the technical model here
       before QAOA is executed.
    */

    if (!window.qPortfolioResult) {

        elements.modelPreview.textContent =

`PROBLEM
────────────────────────────────────────
constrained_portfolio_selection

SOLVER
────────────────────────────────────────
QAOA

DECISION VARIABLES
────────────────────────────────────────
${model.assets.length} binary variables

CARDINALITY CONSTRAINT
────────────────────────────────────────
Σ x_i = ${model.numberOfAssets}

MAX SINGLE ASSET
────────────────────────────────────────
${(model.maxAllocation * 100).toFixed(0)}%

SECTOR LIMIT
────────────────────────────────────────
${model.sectorLimit} assets / sector

RISK PROFILE
────────────────────────────────────────
${model.riskTolerance.toUpperCase()}

CURRENT SELECTION
────────────────────────────────────────
${selectedText}

MODEL STATUS
────────────────────────────────────────
${
    model.validation.valid
        ? "FEASIBLE INPUT"
        : "AWAITING FEASIBLE INPUT"
}`;

    }


    if (elements.modelState) {

        elements.modelState.textContent =
            model.validation.valid
                ? "FEASIBLE MODEL"
                : "WAITING FOR FEASIBLE MODEL";

    }

}


/* ============================================================
   UI UPDATE
   ============================================================ */

function updateInterface() {

    if (!checkRequiredElements()) {
        return;
    }


    elements.selectedCount.textContent =
        state.selectedAssets.size;


    elements.requiredCount.textContent =
        state.maxAssets;


    if (elements.capitalDisplay) {

        elements.capitalDisplay.textContent =
            formatCurrency(
                state.capital
            );

    }


    if (elements.assetCountDisplay) {

        elements.assetCountDisplay.textContent =
            `${state.maxAssets} assets`;

    }


    if (elements.allocationDisplay) {

        elements.allocationDisplay.textContent =
            `${state.maxAllocation}%`;

    }


    if (elements.sectorDisplay) {

        elements.sectorDisplay.textContent =
            state.sectorLimit;

    }


    if (elements.metricVariables) {

        elements.metricVariables.textContent =
            ASSETS.length;

    }


    if (elements.metricCapital) {

        elements.metricCapital.textContent =
            formatCurrency(
                state.capital
            );

    }


    if (elements.metricAllocation) {

        elements.metricAllocation.textContent =
            `${state.maxAllocation}%`;

    }


    if (elements.metricSector) {

        elements.metricSector.textContent =
            state.sectorLimit;

    }


    const validation =
        validateSelection();


    if (validation.valid) {

        elements.selectionWarning.textContent =
            "✓ Selection satisfies the current cardinality and sector constraints.";

        elements.selectionWarning.style.color =
            "var(--accent)";

        elements.optimizeButton.disabled =
            false;

    } else {

        elements.optimizeButton.disabled =
            true;


        if (!validation.exactlyK) {

            elements.selectionWarning.textContent =
                `Select exactly ${state.maxAssets} assets to construct the optimization problem.`;

        } else if (!validation.sectorValid) {

            elements.selectionWarning.textContent =
                "Sector concentration constraint violated. Adjust your selection.";

        }


        elements.selectionWarning.style.color =
            "var(--muted)";

    }


    renderAssets();

    updateModelPreview();

}


/* ============================================================
   RANGE CONTROLS
   ============================================================ */

if (elements.capitalSlider) {

    elements.capitalSlider.addEventListener(
        "input",
        event => {

            state.capital =
                Number(
                    event.target.value
                );

            updateInterface();

        }
    );

}


if (elements.assetCountSlider) {

    elements.assetCountSlider.addEventListener(
        "input",
        event => {

            state.maxAssets =
                Number(
                    event.target.value
                );


            while (
                state.selectedAssets.size >
                state.maxAssets
            ) {

                const selected =
                    [
                        ...state.selectedAssets
                    ];

                const last =
                    selected[
                        selected.length - 1
                    ];

                state.selectedAssets.delete(
                    last
                );

            }


            updateInterface();

        }
    );

}


if (elements.allocationSlider) {

    elements.allocationSlider.addEventListener(
        "input",
        event => {

            state.maxAllocation =
                Number(
                    event.target.value
                );

            updateInterface();

        }
    );

}


if (elements.sectorSlider) {

    elements.sectorSlider.addEventListener(
        "input",
        event => {

            state.sectorLimit =
                Number(
                    event.target.value
                );

            updateInterface();

        }
    );

}


/* ============================================================
   RISK SELECTOR
   ============================================================ */

document
    .querySelectorAll(".risk-option")
    .forEach(
        button => {

            button.addEventListener(
                "click",
                () => {

                    document
                        .querySelectorAll(
                            ".risk-option"
                        )
                        .forEach(
                            item =>
                                item.classList.remove(
                                    "active"
                                )
                        );


                    button.classList.add(
                        "active"
                    );


                    state.riskTolerance =
                        button.dataset.risk;


                    if (elements.riskDisplay) {

                        elements.riskDisplay.textContent =
                            button.dataset.risk.toUpperCase();

                    }


                    updateModelPreview();

                }
            );

        }
    );


/* ============================================================
   REAL QAOA BACKEND
   ============================================================ */

async function runQAOA() {

    const model =
        buildOptimizationModel();


    /* --------------------------------------------------------
       VALIDATION
       -------------------------------------------------------- */

    if (!model.validation.valid) {

        showMessage(
            "Please create a valid portfolio selection first."
        );

        return;

    }


    /* --------------------------------------------------------
       UI: START
       -------------------------------------------------------- */

    elements.optimizeButton.disabled =
        true;


    elements.modelState.textContent =
        "RUNNING QAOA...";


    elements.selectionWarning.textContent =
        "⚛ Quantum optimization is running. Please wait...";


    elements.selectionWarning.style.color =
        "var(--accent)";


    try {

        /* ----------------------------------------------------
           REQUEST PAYLOAD
           ---------------------------------------------------- */

        const payload = {

            capital:
                model.capital,

            numberOfAssets:
                model.numberOfAssets,

            maxAllocation:
                model.maxAllocation,

            sectorLimit:
                model.sectorLimit,

            riskTolerance:
                model.riskTolerance,

            assets:
                model.assets.map(
                    asset => ({

                        id:
                            asset.id,

                        sector:
                            asset.sector,

                        expectedReturn:
                            Number(
                                asset.expectedReturn
                            ),

                        volatility:
                            Number(
                                asset.volatility
                            )

                    })
                )

        };


        console.log(
            "QAOA REQUEST:",
            payload
        );


        /* ----------------------------------------------------
           CALL FASTAPI
           ---------------------------------------------------- */

        const response =
            await fetch(
                `${API_BASE_URL}/qaoa`,
                {

                    method:
                        "POST",

                    headers: {

                        "Content-Type":
                            "application/json"

                    },

                    body:
                        JSON.stringify(
                            payload
                        )

                }
            );


        /* ----------------------------------------------------
           SERVER ERROR
           ---------------------------------------------------- */

        if (!response.ok) {

            const errorText =
                await response.text();


            throw new Error(
                `Backend error ${response.status}: ${errorText}`
            );

        }


        /* ----------------------------------------------------
           PARSE RESULT
           ---------------------------------------------------- */

        const result =
            await response.json();


        console.log(
            "REAL QAOA RESULT:",
            result
        );


        /* ----------------------------------------------------
           STORE RESULT
           ---------------------------------------------------- */

        window.qPortfolioResult =
            result;


        /* ----------------------------------------------------
           DISPLAY RESULT
           ---------------------------------------------------- */

        displayQAOAResult(
            result
        );


    } catch (error) {

        console.error(
            "QAOA ERROR:",
            error
        );


        elements.modelState.textContent =
            "QAOA ERROR";


        elements.selectionWarning.textContent =
            "⚠ Quantum optimization failed: " +
            error.message;


        elements.selectionWarning.style.color =
            "var(--muted)";


    } finally {

        elements.optimizeButton.disabled =
            false;

    }

}


/* ============================================================
   OPTIMIZE BUTTON
   ============================================================ */

if (elements.optimizeButton) {

    elements.optimizeButton.addEventListener(
        "click",
        runQAOA
    );

}


/* ============================================================
   QAOA RESULT DISPLAY
   ============================================================ */

function displayQAOAResult(result) {

    const best =
        result.bestSolution || {};


    /*
       These are the REAL assets returned
       by the FastAPI QAOA endpoint.
    */

    const selectedIds =
        Array.isArray(best.selectedAssets)
            ? best.selectedAssets
            : [];


    const selectedAssets =
        ASSETS.filter(
            asset =>
                selectedIds.includes(
                    asset.id
                )
        );


    /*
       Current backend solves asset selection,
       not continuous portfolio weights.

       Therefore with 4 selected assets,
       equal-weight display = 25% each.
    */

    const allocation =
        selectedAssets.length > 0
            ? 1 / selectedAssets.length
            : 0;


    /*
       Investment amount for each asset.
    */

    const investmentPerAsset =
        state.capital *
        allocation;


    /*
       Expected return of equal-weight portfolio.
    */

    const expectedReturn =
        selectedAssets.length > 0
            ? selectedAssets.reduce(
                (total, asset) =>
                    total +
                    asset.expectedReturn,
                0
            ) / selectedAssets.length
            : 0;


    /*
       Simple average volatility display.

       This is NOT covariance-based portfolio risk.
    */

    const averageRisk =
        selectedAssets.length > 0
            ? selectedAssets.reduce(
                (total, asset) =>
                    total +
                    asset.volatility,
                0
            ) / selectedAssets.length
            : 0;


    /*
       QAOA technical values.
    */

    const probability =
        typeof best.probability === "number"
            ? (
                best.probability *
                100
            ).toFixed(2)
            : "—";


    const energy =
        typeof best.energy === "number"
            ? best.energy.toFixed(6)
            : "—";


    const classical =
        result.classicalBenchmark || {};


    const classicalEnergy =
        typeof classical.energy === "number"
            ? classical.energy.toFixed(6)
            : "—";


    /*
       Build table rows.
    */

    let portfolioRows = "";


    selectedAssets.forEach(
        (asset, index) => {

            portfolioRows += `

                <tr>

                    <td>
                        ${index + 1}
                    </td>

                    <td>

                        <strong>
                            ${asset.id}
                        </strong>

                        <span class="portfolio-company">
                            ${asset.name}
                        </span>

                    </td>

                    <td>
                        ${asset.sector}
                    </td>

                    <td>
                        <strong>
                            ${(allocation * 100).toFixed(1)}%
                        </strong>
                    </td>

                    <td>
                        ${(asset.expectedReturn * 100).toFixed(1)}%
                    </td>

                    <td>
                        ${(asset.volatility * 100).toFixed(1)}%
                    </td>

                    <td>
                        ${formatCurrency(
                            investmentPerAsset
                        )}
                    </td>

                </tr>

            `;

        }
    );


    /*
       Safety fallback.
    */

    if (selectedAssets.length === 0) {

        portfolioRows = `

            <tr>

                <td colspan="7">

                    No selected assets were returned
                    by the QAOA solver.

                </td>

            </tr>

        `;

    }


    /*
       Render final portfolio.
    */

    elements.modelPreview.innerHTML = `

        <div class="portfolio-result">


            <!-- ==========================================
                 RESULT HEADER
            =========================================== -->

            <div class="portfolio-result-header">

                <div>

                    <div class="result-label">
                        FINAL QUANTUM PORTFOLIO
                    </div>

                    <h2>
                        QAOA OPTIMIZATION COMPLETE
                    </h2>

                    <p>
                        ${selectedAssets.length}
                        stocks selected from
                        ${ASSETS.length}
                        available assets.
                    </p>

                </div>


                <div class="result-status">
                    ✓ OPTIMIZED
                </div>

            </div>


            <!-- ==========================================
                 SUMMARY
            =========================================== -->

            <div class="portfolio-summary">


                <div class="portfolio-stat">

                    <span>
                        SELECTED STOCKS
                    </span>

                    <strong>
                        ${selectedAssets.length}
                    </strong>

                    <small>
                        final portfolio
                    </small>

                </div>


                <div class="portfolio-stat">

                    <span>
                        ALLOCATION
                    </span>

                    <strong>
                        ${(allocation * 100).toFixed(1)}%
                    </strong>

                    <small>
                        per selected stock
                    </small>

                </div>


                <div class="portfolio-stat">

                    <span>
                        EXPECTED RETURN
                    </span>

                    <strong>
                        ${(expectedReturn * 100).toFixed(2)}%
                    </strong>

                    <small>
                        equal-weight portfolio
                    </small>

                </div>


                <div class="portfolio-stat">

                    <span>
                        PORTFOLIO RISK
                    </span>

                    <strong>
                        ${(averageRisk * 100).toFixed(2)}%
                    </strong>

                    <small>
                        average volatility
                    </small>

                </div>

            </div>


            <!-- ==========================================
                 INVESTMENT SUMMARY
            =========================================== -->

            <div class="final-portfolio-box">

                <div class="result-label">
                    INVESTMENT PLAN
                </div>

                <div class="final-assets">

                    ${
                        selectedAssets.length
                            ? selectedAssets
                                .map(
                                    asset =>
                                        `
                                        <span class="final-asset">
                                            ${asset.id}
                                        </span>
                                        `
                                )
                                .join("")
                            : `
                                <span>
                                    No assets selected
                                </span>
                              `
                    }

                </div>


                <p>

                    Total capital:

                    <strong>
                        ${formatCurrency(
                            state.capital
                        )}
                    </strong>

                    &nbsp; • &nbsp;

                    ${selectedAssets.length}
                    stocks

                    &nbsp; • &nbsp;

                    <strong>
                        ${(allocation * 100).toFixed(1)}%
                    </strong>
                    allocation each

                </p>

            </div>


            <!-- ==========================================
                 PORTFOLIO TABLE
            =========================================== -->

            <div class="portfolio-table-wrapper">

                <div class="result-label">
                    SELECTED PORTFOLIO
                </div>


                <table class="portfolio-table">

                    <thead>

                        <tr>

                            <th>
                                #
                            </th>

                            <th>
                                STOCK
                            </th>

                            <th>
                                SECTOR
                            </th>

                            <th>
                                ALLOCATION
                            </th>

                            <th>
                                EXPECTED RETURN
                            </th>

                            <th>
                                RISK
                            </th>

                            <th>
                                INVESTMENT
                            </th>

                        </tr>

                    </thead>


                    <tbody>

                        ${portfolioRows}

                    </tbody>

                </table>

            </div>


            <!-- ==========================================
                 QAOA TECHNICAL DETAILS
            =========================================== -->

            <details class="qaoa-details">

                <summary>
                    QAOA TECHNICAL RESULTS
                </summary>


                <div class="technical-grid">


                    <div>

                        <span>
                            ALGORITHM
                        </span>

                        <strong>
                            ${result.algorithm || "QAOA"}
                        </strong>

                    </div>


                    <div>

                        <span>
                            QUANTUM DEPTH
                        </span>

                        <strong>
                            ${result.depth ?? "—"}
                        </strong>

                    </div>


                    <div>

                        <span>
                            QUBITS
                        </span>

                        <strong>
                            ${result.qubits ?? ASSETS.length}
                        </strong>

                    </div>


                    <div>

                        <span>
                            SHOTS
                        </span>

                        <strong>
                            ${result.shots ?? "—"}
                        </strong>

                    </div>


                    <div>

                        <span>
                            BEST BITSTRING
                        </span>

                        <strong>
                            ${best.bitstring || "—"}
                        </strong>

                    </div>


                    <div>

                        <span>
                            QAOA ENERGY
                        </span>

                        <strong>
                            ${energy}
                        </strong>

                    </div>


                    <div>

                        <span>
                            MEASUREMENT PROBABILITY
                        </span>

                        <strong>
                            ${probability}%
                        </strong>

                    </div>


                    <div>

                        <span>
                            CLASSICAL ENERGY
                        </span>

                        <strong>
                            ${classicalEnergy}
                        </strong>

                    </div>


                    <div>

                        <span>
                            MATCHES CLASSICAL
                        </span>

                        <strong>
                            ${
                                result.comparison &&
                                result.comparison.matchesClassical
                                    ? "YES"
                                    : "NO"
                            }
                        </strong>

                    </div>

                </div>

            </details>


            <!-- ==========================================
                 NOTE
            =========================================== -->

            <div class="portfolio-note">

                <strong>
                    Allocation note:
                </strong>

                The QAOA backend currently determines
                the optimal stock combination.

                Since the backend does not return
                continuous allocation weights,
                the displayed allocation is equal-weighted.

                Therefore, with 4 selected stocks:

                <strong>
                    25% each
                </strong>

                and the four investments total:

                <strong>
                    ${formatCurrency(
                        state.capital
                    )}
                </strong>.

            </div>


        </div>

    `;


    /*
       Update status.
    */

    if (elements.modelState) {

        elements.modelState.textContent =
            "QAOA COMPLETE";

    }


    if (elements.selectionWarning) {

        elements.selectionWarning.textContent =
            "✓ Quantum optimization completed successfully.";

        elements.selectionWarning.style.color =
            "var(--accent)";

    }


    /*
       Keep result available globally.
    */

    window.qPortfolioResult =
        result;


    console.log(
        "Best QAOA solution:",
        best
    );

    console.log(
        "Selected assets:",
        selectedAssets
    );

    console.log(
        "Classical benchmark:",
        classical
    );

}


/* ============================================================
   MESSAGE HELPER
   ============================================================ */

function showMessage(message) {

    if (!elements.selectionWarning) {
        return;
    }

    elements.selectionWarning.textContent =
        message;

}


/* ============================================================
   INITIALIZE
   ============================================================ */

function initializePortfolio() {

    if (!checkRequiredElements()) {

        console.error(
            "Q-PORTFOLIO initialization failed."
        );

        return;

    }


    renderAssets();

    updateInterface();


    console.log(
        "%cQ-PORTFOLIO",
        "font-size:24px;font-weight:bold"
    );


    console.log(
        "Portfolio configuration engine initialized."
    );


    console.log(
        "QAOA API:",
        `${API_BASE_URL}/qaoa`
    );

}


initializePortfolio();