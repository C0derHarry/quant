export type Category =
  | 'Valuation'
  | 'Quality'
  | 'Profitability'
  | 'Value'
  | 'Growth'
  | 'Risk'
  | 'Momentum'
  | 'Portfolio'
  | 'Factor'
  | 'Volatility'
  | 'Technical'
  | 'ML / Regime'
  | 'Strategy'

export type Difficulty = 'Low' | 'Medium' | 'High'

export interface ModelEntry {
  id: string
  name: string
  category: Category
  description: string
  formula: string
  inputs: string[]
  measures: string
  interpretation: string
  advantages: string[]
  limitations: string[]
  useCases: string[]
  tier: 'free' | 'premium'
  implemented: boolean
  difficulty: Difficulty
  dataRequired: string[]
}

const catalog: ModelEntry[] = [
  // ─── SCREENERS (implemented) ──────────────────────────────────
  {
    id: 'magic-formula',
    name: 'Magic Formula (Greenblatt)',
    category: 'Value',
    description:
      "Joel Greenblatt's quantitative strategy that ranks stocks by earnings yield and return on capital, then combines the ranks to find high-quality businesses trading at cheap prices.",
    formula:
      'EY = EBIT / Enterprise Value\nROC = EBIT / Invested Capital\nMagic Score = Rank(EY) + Rank(ROC)',
    inputs: ['EBIT', 'Enterprise Value', 'Invested Capital'],
    measures: 'Combination of cheapness (earnings yield) and quality (return on capital)',
    interpretation:
      'Lower combined rank = better. Top-ranked stocks are both cheap and high-quality. Greenblatt recommends buying the top 20–30 names and holding for one year.',
    advantages: [
      'Systematic and removes emotional bias',
      'Combines quality and value, avoiding value traps',
      'Long track record of outperformance in US markets',
    ],
    limitations: [
      'Works best over 3–5 year horizons; short-term results can be disappointing',
      'Does not account for debt quality or sector differences',
      'Earnings may be cyclical, distorting the signal',
    ],
    useCases: ['Annual stock selection', 'Quantitative value screening'],
    tier: 'free',
    implemented: true,
    difficulty: 'Medium',
    dataRequired: ['Income statement (EBIT)', 'Balance sheet (Total assets, current liabilities)', 'Market cap'],
  },
  {
    id: 'qarp',
    name: 'QARP (Quality at a Reasonable Price)',
    category: 'Quality',
    description:
      'A multi-criteria screen combining quality metrics (ROE, leverage) with valuation (forward P/E vs trailing P/E) to identify improving businesses that are not yet overpriced.',
    formula:
      'ROE = Net Income / Shareholders Equity\nD/E = Total Debt / Equity\nValuation = Forward P/E vs Trailing P/E\nVerdict: BUY / WATCH / AVOID',
    inputs: ['Net Income', 'Shareholders Equity', 'Total Debt', 'Forward EPS estimate', 'Trailing EPS'],
    measures: 'Combined quality and valuation score',
    interpretation:
      'BUY = high ROE, manageable leverage, and P/E expansion (earnings growing). WATCH = one criterion weak. AVOID = poor quality or expensive.',
    advantages: [
      'Balances quality with valuation — avoids overpaying for quality',
      'Easy to interpret; verdict is actionable',
      'Filters out highly leveraged businesses',
    ],
    limitations: [
      'ROE can be inflated by share buybacks or high leverage',
      'Forward EPS estimates may be inaccurate',
      'Does not capture moat or management quality',
    ],
    useCases: ['Mid-term stock selection', 'Quality growth screening'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Balance sheet', 'Income statement', 'Analyst EPS estimates'],
  },

  // ─── RISK METRICS (implemented) ──────────────────────────────
  {
    id: 'sharpe-ratio',
    name: 'Sharpe Ratio',
    category: 'Risk',
    description:
      'The most widely used risk-adjusted return metric. Measures excess return per unit of total volatility, normalising returns against a risk-free rate.',
    formula: 'Sharpe = (R_p - R_f) / σ_p\nwhere R_f = 7% (Indian T-bill benchmark)',
    inputs: ['Portfolio daily returns', 'Risk-free rate (7%)'],
    measures: 'Return per unit of total risk (standard deviation)',
    interpretation:
      'Sharpe > 1 is generally good; > 2 is excellent. Below 0 means the portfolio underperforms the risk-free rate. Compare between strategies, not in isolation.',
    advantages: [
      'Universal metric — comparable across strategies and asset classes',
      'Simple to compute and interpret',
      'Penalises both upside and downside volatility equally',
    ],
    limitations: [
      'Penalises upside volatility (good returns), not just downside',
      'Assumes returns are normally distributed (markets have fat tails)',
      'Sensitive to the choice of risk-free rate and time period',
    ],
    useCases: ['Portfolio comparison', 'Strategy evaluation', 'Manager assessment'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Daily price returns', 'Risk-free rate'],
  },
  {
    id: 'sortino-ratio',
    name: 'Sortino Ratio',
    category: 'Risk',
    description:
      'An improvement on the Sharpe Ratio that only penalises downside volatility, treating upside volatility as desirable rather than risky.',
    formula: 'Sortino = (R_p - R_f) / σ_down\nwhere σ_down = std dev of negative returns only',
    inputs: ['Portfolio daily returns', 'Risk-free rate'],
    measures: 'Return per unit of downside risk only',
    interpretation:
      'Higher is better. Sortino > Sharpe usually indicates the volatility is mostly on the upside (good). Preferred metric for asymmetric strategies.',
    advantages: [
      'Does not penalise positive surprises',
      'Better for strategies with asymmetric return profiles (options, momentum)',
      'More realistic representation of investor psychology',
    ],
    limitations: [
      'Fewer data points (only negative returns) makes it noisier',
      'Less widely understood than Sharpe for external communication',
    ],
    useCases: ['Momentum strategies', 'Asymmetric return strategies', 'Portfolio evaluation'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Daily price returns', 'Risk-free rate'],
  },
  {
    id: 'calmar-ratio',
    name: 'Calmar Ratio',
    category: 'Risk',
    description:
      'Measures return relative to the worst historical loss. Useful for evaluating strategies where drawdowns are especially painful (leveraged or trend-following).',
    formula: 'Calmar = CAGR / |Max Drawdown|',
    inputs: ['CAGR', 'Maximum Drawdown'],
    measures: 'Annualised return relative to worst peak-to-trough loss',
    interpretation:
      'Calmar > 1 means the strategy earns more per year than its worst drawdown. Higher is better. Common benchmark: > 0.5 is acceptable for trend strategies.',
    advantages: [
      'Directly captures tail risk that Sharpe misses',
      'Intuitive for long-only investors who care about worst-case losses',
    ],
    limitations: [
      'Depends heavily on the time period chosen',
      'Max drawdown can be a single extreme event that distorts the ratio',
    ],
    useCases: ['Trend following strategies', 'Risk-aware portfolio comparison'],
    tier: 'premium',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Daily price returns'],
  },
  {
    id: 'jensens-alpha',
    name: "Jensen's Alpha",
    category: 'Risk',
    description:
      "Measures a portfolio's excess return above what the CAPM predicts given the portfolio's market exposure (beta). A positive alpha indicates skill or structural edge.",
    formula: 'α = R_p - [R_f + β(R_m - R_f)]',
    inputs: ['Portfolio daily returns', 'Benchmark returns (NIFTY 50)', 'Risk-free rate', 'Beta'],
    measures: 'Excess return beyond CAPM expectation',
    interpretation:
      'Alpha > 0 means the portfolio delivered more than its market exposure predicts. Alpha < 0 is underperformance. Annualised and presented in percentage terms.',
    advantages: [
      'Accounts for market exposure — fairly rewards high-beta strategies',
      'Widely understood in institutional finance',
    ],
    limitations: [
      'CAPM is a simplified model; true alpha may reflect other factors (size, value)',
      'Requires a long history for statistical significance',
    ],
    useCases: ['Active fund evaluation', 'Strategy benchmarking'],
    tier: 'premium',
    implemented: true,
    difficulty: 'Medium',
    dataRequired: ['Daily price returns', 'Benchmark (NIFTY 50) returns'],
  },
  {
    id: 'beta',
    name: 'Beta',
    category: 'Risk',
    description:
      'Measures systematic market risk — how much the portfolio or stock moves relative to the overall market. A core concept from the Capital Asset Pricing Model (CAPM).',
    formula: 'β = Cov(R_p, R_m) / Var(R_m)',
    inputs: ['Portfolio / stock returns', 'Market benchmark returns (NIFTY 50)'],
    measures: 'Sensitivity to market movements',
    interpretation:
      'Beta = 1 moves with the market. Beta > 1 is more volatile (amplifies moves). Beta < 1 is defensive. Beta < 0 is inversely correlated (rare; e.g., gold in some regimes).',
    advantages: [
      'Simple and universally understood',
      'Useful for constructing market-neutral or low-beta portfolios',
    ],
    limitations: [
      'Beta is backward-looking and changes over time',
      'Assumes linear relationship with market; breaks down in crises',
    ],
    useCases: ['Portfolio construction', 'Risk budgeting', 'Stock classification'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Daily price returns', 'Benchmark returns'],
  },
  {
    id: 'max-drawdown',
    name: 'Maximum Drawdown',
    category: 'Risk',
    description:
      'The largest peak-to-trough decline in portfolio value during a given period. The definitive measure of historical downside risk.',
    formula: 'Max DD = max over all t of [(Peak value up to t) - (Value at t)] / (Peak value up to t)',
    inputs: ['Daily or monthly portfolio NAV or price series'],
    measures: 'Worst historical loss from a peak before recovery',
    interpretation:
      'Expressed as a negative percentage. -20% means the portfolio fell 20% from its highest point before recovering. Lower (less negative) is better.',
    advantages: [
      'Directly shows the worst scenario a real investor would have experienced',
      'No distributional assumptions — purely empirical',
    ],
    limitations: [
      'A single extreme event can make a strategy look worse than it is',
      'Does not capture duration of the drawdown',
    ],
    useCases: ['Risk reporting', 'Strategy comparison', 'Stress testing'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Price or NAV series'],
  },
  {
    id: 'cagr',
    name: 'CAGR',
    category: 'Risk',
    description:
      'Compound Annual Growth Rate — the smoothed annual rate of return that would produce the same end value from the starting value over the given period.',
    formula: 'CAGR = (End Value / Start Value)^(1/n) - 1\nwhere n = number of years',
    inputs: ['Start value', 'End value', 'Number of years'],
    measures: 'Annualised total return, compounding assumed',
    interpretation:
      'The go-to single number for comparing strategy or stock performance across different time periods. Always compare CAGR alongside volatility and drawdown.',
    advantages: [
      'Normalises returns across different time periods',
      'Intuitive and widely communicated',
    ],
    limitations: [
      'Ignores path — a volatile strategy with the same CAGR is far riskier',
      'Sensitive to start and end date selection',
    ],
    useCases: ['Performance reporting', 'Long-term comparison', 'Goal planning'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Price or NAV series'],
  },
  {
    id: 'var',
    name: 'Value at Risk (VaR)',
    category: 'Risk',
    description:
      'Estimates the maximum loss a portfolio is likely to suffer over a given time horizon at a specified confidence level. A standard risk management metric.',
    formula: '95% 1-day VaR: the 5th percentile of the portfolio return distribution\n(Both parametric Student-t and bootstrap methods used)',
    inputs: ['Daily portfolio returns', 'Confidence level (95%)'],
    measures: 'Potential loss threshold with a given probability',
    interpretation:
      'A 1-day VaR of -2% at 95% means there is a 5% chance the portfolio loses more than 2% in a single day. Used for position sizing and risk limits.',
    advantages: [
      'Regulatory standard (Basel III uses VaR)',
      'Translates statistical risk into a monetary loss figure',
    ],
    limitations: [
      'Understates tail risk (the 5% of cases beyond VaR)',
      'Assumes returns have a stable distribution; breaks in crises',
    ],
    useCases: ['Daily risk monitoring', 'Position sizing', 'Regulatory reporting'],
    tier: 'premium',
    implemented: true,
    difficulty: 'Medium',
    dataRequired: ['Daily portfolio returns'],
  },
  {
    id: 'cvar',
    name: 'Conditional VaR (CVaR / Expected Shortfall)',
    category: 'Risk',
    description:
      'The average loss in the worst scenarios beyond the VaR threshold. Captures tail risk that VaR ignores and is the preferred metric in modern risk management.',
    formula: 'CVaR = E[Loss | Loss > VaR]\n(Average of returns in the worst 5% tail)',
    inputs: ['Daily portfolio returns', 'Confidence level (95%)'],
    measures: 'Expected loss given a tail event has occurred',
    interpretation:
      'CVaR is always worse (more negative) than VaR. A CVaR of -4% at 95% means when losses exceed VaR, the average loss is 4%. Lower magnitude is better.',
    advantages: [
      'Captures the severity of tail events, not just the probability',
      'Coherent risk measure (unlike VaR) — sub-additive and convex',
      'Preferred by practitioners for portfolio optimisation under tail risk',
    ],
    limitations: [
      'Noisier than VaR due to fewer data points in the tail',
      'Harder to communicate to non-technical stakeholders',
    ],
    useCases: ['Tail risk management', 'Stress testing', 'Optimal portfolio construction'],
    tier: 'premium',
    implemented: true,
    difficulty: 'Medium',
    dataRequired: ['Daily portfolio returns'],
  },

  // ─── VOLATILITY MODELS (implemented) ─────────────────────────
  {
    id: 'ewma',
    name: 'EWMA Volatility',
    category: 'Volatility',
    description:
      "RiskMetrics-style exponentially weighted volatility model. More responsive than rolling historical volatility by giving more weight to recent observations via a decay factor (λ).",
    formula: 'σ²_t = λ·σ²_{t-1} + (1-λ)·r²_t\nOptimal λ estimated via maximum likelihood (default 0.94)',
    inputs: ['Daily price returns', 'Decay factor λ (default 0.94, MLE-optimised)'],
    measures: 'Current volatility estimate with exponential memory decay',
    interpretation:
      'Annualised by × √252. Higher λ = longer memory (slower to react). Half-life = log(0.5)/log(λ) days. When EWMA spikes, risk is elevated. Used for dynamic position sizing.',
    advantages: [
      'Reacts faster to volatility spikes than rolling window methods',
      'Optimal λ is data-driven via MLE',
      'Industry standard (JP Morgan RiskMetrics, 1994)',
    ],
    limitations: [
      'No mean reversion — assumes current vol level persists',
      'Single parameter model; cannot capture volatility clustering persistence',
    ],
    useCases: ['Dynamic position sizing', 'Risk monitoring', 'Stop-loss calibration'],
    tier: 'premium',
    implemented: true,
    difficulty: 'Medium',
    dataRequired: ['Daily close prices (minimum 60 days)'],
  },
  {
    id: 'garch',
    name: 'GARCH(p,q)',
    category: 'Volatility',
    description:
      'Generalised AutoRegressive Conditional Heteroskedasticity. The standard econometric model for capturing volatility clustering — the empirical observation that large moves follow large moves.',
    formula: 'σ²_t = ω + Σᵢ αᵢ·ε²_{t-i} + Σⱼ βⱼ·σ²_{t-j}\nModel selection via joint AIC+BIC across grid (p,q) ∈ {1..3}²',
    inputs: ['Daily log returns', 'GARCH order (p, q) — auto-selected'],
    measures: 'Conditional variance forecasts with volatility clustering',
    interpretation:
      'Persistence (α+β close to 1) means shocks decay slowly. GARCH forecasts 1–7 day volatility ahead. Used to size positions and set dynamic stops.',
    advantages: [
      'Captures volatility clustering and mean reversion',
      'Forecasts forward volatility, not just current level',
      'Statistically well-founded with formal significance tests',
    ],
    limitations: [
      'Symmetric — treats positive and negative shocks equally (asymmetry needs EGARCH/GJR)',
      'Parameter estimation requires long history (200+ days)',
      'Forecast accuracy degrades beyond 5–7 days',
    ],
    useCases: ['Volatility forecasting', 'Options pricing', 'Risk capital estimation'],
    tier: 'premium',
    implemented: true,
    difficulty: 'High',
    dataRequired: ['Daily close prices (minimum 200 days)'],
  },
  {
    id: 'dcc-garch',
    name: 'DCC-GARCH',
    category: 'Volatility',
    description:
      'Dynamic Conditional Correlation GARCH. Extends GARCH to multi-asset portfolios by estimating time-varying correlations between assets, improving covariance matrix estimates for optimisation.',
    formula: 'H_t = D_t · R_t · D_t\nD_t = diag(GARCH(1,1) vols per asset)\nR_t = DCC dynamics on standardised residuals\nQ̄ = Ledoit-Wolf shrinkage covariance',
    inputs: ['Daily returns for multiple assets', 'DCC parameters (a, b) via L-BFGS-B'],
    measures: 'Time-varying covariance matrix for portfolio construction',
    interpretation:
      'Correlations rise in crises (risk-on/off). DCC captures this dynamically, giving better diversification estimates than static historical correlation for portfolio optimisation.',
    advantages: [
      'Dynamic correlations are more realistic than static estimates',
      'Ledoit-Wolf shrinkage prevents ill-conditioned matrices',
      'Feeds directly into Black-Litterman and MVO',
    ],
    limitations: [
      'Computationally intensive for large universes (n > 30 assets)',
      'Assumes elliptical distributions; underestimates tail co-movement',
      'Parameters can be unstable in regime transitions',
    ],
    useCases: ['Portfolio optimisation', 'Correlation-adjusted risk', 'Pairs trading'],
    tier: 'premium',
    implemented: true,
    difficulty: 'High',
    dataRequired: ['Daily close prices for all assets in portfolio (minimum 252 days)'],
  },

  // ─── PORTFOLIO MODELS (implemented) ──────────────────────────
  {
    id: 'black-litterman',
    name: 'Black-Litterman',
    category: 'Portfolio',
    description:
      'A Bayesian framework that blends market equilibrium expected returns (from market capitalisation weights) with investor views from quantitative models (regimes, momentum signals).',
    formula: 'μ_BL = [(τΣ)⁻¹ + PᵀΩ⁻¹P]⁻¹ · [(τΣ)⁻¹π + PᵀΩ⁻¹q]\nπ = λΣw_mkt (implied equilibrium)\nτ = 0.5 (prior uncertainty)',
    inputs: ['Market cap weights', 'DCC-GARCH covariance matrix', 'HMM regime signals', 'Momentum views', 'Risk aversion λ'],
    measures: 'Posterior expected returns blending market prior and model views',
    interpretation:
      'Outputs revised expected returns that combine market-implied priors with model signals. High-conviction bullish regime view tilts expected return upward for that asset.',
    advantages: [
      'Overcomes the sensitivity of pure MVO to return estimates',
      'Allows systematic incorporation of quantitative views',
      'Produces more stable, diversified weights than unconstrained MVO',
    ],
    limitations: [
      'Views (Ω matrix) are hard to specify precisely',
      'Still relies on a covariance matrix estimate which can be noisy',
      'Black box relative to pure factor models',
    ],
    useCases: ['Institutional portfolio construction', 'Quantitative asset allocation'],
    tier: 'premium',
    implemented: true,
    difficulty: 'High',
    dataRequired: ['Market cap data', 'Historical returns (2+ years)', 'Regime signals'],
  },
  {
    id: 'mvo',
    name: 'Mean-Variance Optimisation (MVO)',
    category: 'Portfolio',
    description:
      "Harry Markowitz's foundational portfolio theory. Finds the portfolio weights that maximise Sharpe Ratio (or minimise variance for a target return) given expected returns and a covariance matrix.",
    formula: 'Maximise: (wᵀμ - R_f) / √(wᵀΣw)\nSubject to: Σw = 1, w_i ≤ 40%, with L2 regularisation penalty λ||w||²',
    inputs: ['Expected returns (from Black-Litterman)', 'Covariance matrix (DCC-GARCH)', 'Max weight constraint (40%)'],
    measures: 'Maximum Sharpe portfolio weights',
    interpretation:
      'Outputs percentage weights per asset. L2 regularisation prevents extreme concentration. Multiple starting points (equal-weight, inverse-vol, momentum) reduce local optima.',
    advantages: [
      'Theoretically optimal under normality assumptions',
      'Easily adaptable (add constraints, shrinkage, regularisation)',
      'Output is interpretable and directly actionable',
    ],
    limitations: [
      'Extremely sensitive to return estimates ("garbage in, garbage out")',
      'Historical covariance is noisy; DCC helps but does not eliminate this',
      'Concentrated weights without regularisation',
    ],
    useCases: ['Portfolio construction', 'Asset allocation', 'Index replication'],
    tier: 'premium',
    implemented: true,
    difficulty: 'High',
    dataRequired: ['Historical returns (minimum 1 year)', 'Expected returns'],
  },
  {
    id: 'risk-parity',
    name: 'Risk Parity',
    category: 'Portfolio',
    description:
      'Allocates capital so that each asset contributes equally to total portfolio risk (not equally in dollar terms). Assets with lower volatility receive higher weights.',
    formula: 'Minimise: Σᵢ Σⱼ (RC_i - RC_j)²\nRC_i = w_i · (Σw)_i / (wᵀΣw) (Risk Contribution of asset i)',
    inputs: ['Covariance matrix', 'Asset returns'],
    measures: 'Equal risk contribution weights',
    interpretation:
      'Outputs weights and risk contributions per asset (each should be ~1/n of total risk). A 4-asset portfolio: each contributes 25% of risk. More defensive than MVO during downturns.',
    advantages: [
      'Does not require expected return estimates (only covariance)',
      'Diversifies risk, not capital — avoids concentration in low-vol assets',
      'Historically robust across market regimes',
    ],
    limitations: [
      'Still depends on covariance estimates which are noisy',
      'Low-vol assets get over-weighted; may need leverage to hit return targets',
    ],
    useCases: ['All-weather portfolios', 'Multi-asset allocation', 'Alternative to 60/40'],
    tier: 'premium',
    implemented: true,
    difficulty: 'High',
    dataRequired: ['Historical returns (minimum 1 year)'],
  },
  {
    id: 'efficient-frontier',
    name: 'Efficient Frontier',
    category: 'Portfolio',
    description:
      'The set of optimal portfolios that offer the highest expected return for each level of risk (or lowest risk for each level of return). Foundation of Modern Portfolio Theory.',
    formula: 'Parametric sweep from min-variance to max-return\n50 portfolios computed; Ledoit-Wolf covariance shrinkage applied throughout',
    inputs: ['Historical returns (all assets)', 'Target return or risk level'],
    measures: 'Return-risk tradeoff surface; identifies min-variance and max-Sharpe portfolios',
    interpretation:
      'Portfolios on the frontier are "efficient." Any portfolio below the frontier is dominated. The max-Sharpe point is the tangency portfolio on the Capital Market Line.',
    advantages: [
      'Visual representation of the return-risk tradeoff',
      'Shows the cost of adding constraints (reduced frontier)',
      'Identifies the maximum Sharpe portfolio analytically',
    ],
    limitations: [
      'Based on historical estimates — future frontier may differ significantly',
      'Assumes returns are jointly normally distributed',
    ],
    useCases: ['Portfolio analysis', 'Investor education', 'Constraint evaluation'],
    tier: 'premium',
    implemented: true,
    difficulty: 'High',
    dataRequired: ['Historical returns for all assets (minimum 1 year)'],
  },

  // ─── ML / REGIME (implemented) ───────────────────────────────
  {
    id: 'hmm-regimes',
    name: 'HMM Regime Detection',
    category: 'ML / Regime',
    description:
      '3-state Gaussian Hidden Markov Model that classifies market conditions as Bull, Sideways, or Bear using return, volatility, and trend features. Drives regime-conditioned portfolio weights.',
    formula: 'P(S_t | S_{t-1}) = Transition matrix (sticky, p_stay=0.955)\nFeatures: [daily return, 20-day rolling vol, 20-day cumulative return]\nMultiple EM restarts; means anchored at 16th/50th/84th percentiles\nPosterior smoothed via EMA(span=10); confidence threshold 55%',
    inputs: ['Daily close prices (minimum 252 days per asset)', 'Number of states (3)'],
    measures: 'Probability of each market regime at each point in time',
    interpretation:
      'Bull = positive trend, low vol. Sideways = range-bound, moderate vol. Bear = negative trend, high vol. Regime probabilities are used to tilt portfolio weights in optimisation.',
    advantages: [
      'Captures non-linear regime transitions that linear models miss',
      'Regime-conditioned expected returns improve portfolio construction',
      'EMA smoothing prevents whipsaw regime switching',
    ],
    limitations: [
      'Number of states is a hyperparameter requiring judgement',
      'Regimes are labelled post-hoc; real-time classification lags',
      'HMM assumes Gaussian emissions — fat tails in bear regimes are underestimated',
    ],
    useCases: ['Regime-aware asset allocation', 'Risk signal generation', 'Strategy switching'],
    tier: 'premium',
    implemented: true,
    difficulty: 'High',
    dataRequired: ['Daily close prices (minimum 252 days)'],
  },
  {
    id: 'ml-signal',
    name: 'ML Gradient Boosting Signal',
    category: 'ML / Regime',
    description:
      'A calibrated gradient boosting classifier trained to predict the 5-day forward return direction. Uses 36 engineered features (momentum, vol, technical indicators with 1/2/5-day lags).',
    formula: 'Target: P(R_{t+5} > 0 | features_t)\n12 base features × 3 lags = 36 total\nModel: GradientBoostingClassifier + CalibratedClassifierCV (isotonic)\nChronological train/test split (80/20); StandardScaler preprocessing',
    inputs: ['RSI, MACD histogram, Bollinger %B, ADX, DI spread, ATR/Close, 5d/20d/60d returns, EWMA vol ratio'],
    measures: 'Probability of positive 5-day return',
    interpretation:
      'P(up) > 0.6 = High Conviction Long. 0.5–0.6 = Long. 0.4–0.5 = Neutral. 0.35–0.4 = Short. < 0.35 = High Conviction Short. Model is calibrated — probabilities are reliable (low Brier score).',
    advantages: [
      'Non-linear relationships captured (interactions between features)',
      'Probability-calibrated output enables position sizing',
      'Updated daily; per-ticker models via joblib caching',
    ],
    limitations: [
      'Past patterns may not persist (non-stationary markets)',
      'Requires sufficient per-ticker history (1+ year)',
      'May overfit on low-volume or illiquid stocks',
    ],
    useCases: ['Stock filtering', 'Signal-augmented portfolio optimisation', 'Regime confirmation'],
    tier: 'premium',
    implemented: true,
    difficulty: 'High',
    dataRequired: ['Daily close prices with OHLCV (minimum 252 days)'],
  },

  // ─── TECHNICAL INDICATORS (implemented) ──────────────────────
  {
    id: 'rsi',
    name: 'RSI (Relative Strength Index)',
    category: 'Technical',
    description:
      'Momentum oscillator measuring the speed and magnitude of price changes. Ranges from 0 to 100; extremes signal potential trend exhaustion.',
    formula: 'RSI = 100 - 100/(1 + RS)\nRS = Avg Gain (14 periods) / Avg Loss (14 periods)',
    inputs: ['Daily close prices', 'Period (default 14)'],
    measures: 'Momentum and potential overbought/oversold conditions',
    interpretation:
      'RSI > 70: potentially overbought (momentum may exhaust). RSI < 30: potentially oversold (may find support). RSI 40–60 = neutral momentum zone.',
    advantages: ['Bounded oscillator (0–100) — easy to compare', 'Identifies divergences with price'],
    limitations: ['In trending markets, RSI can stay overbought/oversold for extended periods', 'Lagging indicator'],
    useCases: ['Entry/exit timing', 'Divergence detection', 'Momentum confirmation'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Daily close prices (minimum 30 days)'],
  },
  {
    id: 'macd',
    name: 'MACD',
    category: 'Technical',
    description:
      'Moving Average Convergence Divergence. Trend-following momentum indicator showing the relationship between two EMAs and their signal line.',
    formula: 'MACD Line = EMA(12) - EMA(26)\nSignal Line = EMA(9) of MACD\nHistogram = MACD - Signal',
    inputs: ['Daily close prices'],
    measures: 'Trend direction, strength, and momentum shifts',
    interpretation:
      'MACD crossing above signal = bullish (buy signal). Crossing below = bearish (sell signal). Histogram crossing zero confirms momentum shift. Divergences are high-conviction signals.',
    advantages: ['Combines trend and momentum in one indicator', 'Widely used; well-researched'],
    limitations: ['Lagging — signals come after the move has started', 'Whipsaw-prone in ranging markets'],
    useCases: ['Trend confirmation', 'Entry/exit signals', 'Momentum measurement'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Daily close prices (minimum 60 days)'],
  },
  {
    id: 'bollinger-bands',
    name: 'Bollinger Bands',
    category: 'Technical',
    description:
      'Volatility bands placed above and below a simple moving average. Width expands during high volatility and contracts during low volatility, providing dynamic support/resistance.',
    formula: 'Middle Band = SMA(20)\nUpper Band = SMA(20) + 2σ\nLower Band = SMA(20) - 2σ\n%B = (Price - Lower) / (Upper - Lower)',
    inputs: ['Daily close prices', 'Period (20)', 'Standard deviations (2)'],
    measures: 'Volatility-adjusted price levels and overbought/oversold conditions',
    interpretation:
      '%B > 1: price above upper band (overbought / breakout). %B < 0: price below lower band (oversold / breakdown). Bandwidth = vol normalised spread; squeeze precedes expansion.',
    advantages: ['Self-adjusting to volatility', 'Works across timeframes and instruments'],
    limitations: ['Not a standalone trading system', 'Trend-following works better in trending markets than mean-reversion'],
    useCases: ['Volatility squeezes', 'Mean reversion setups', 'Breakout confirmation'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Daily close prices (minimum 30 days)'],
  },
  {
    id: 'adx',
    name: 'ADX (Average Directional Index)',
    category: 'Technical',
    description:
      'Measures trend strength without indicating direction. Values above 25 signal a trending market; below 20 indicates ranging (choppy) conditions.',
    formula: 'DX = 100 × |+DI - -DI| / (+DI + -DI)\nADX = Smoothed EMA(14) of DX\n+DI and -DI derived from true range components',
    inputs: ['Daily OHLCV', 'Period (default 14)'],
    measures: 'Trend strength (not direction)',
    interpretation:
      'ADX < 20: weak/absent trend (avoid trend strategies). ADX 20–25: developing trend. ADX > 25: strong trend. ADX > 40: very strong trend. Use with +DI/-DI for direction.',
    advantages: ['Excellent filter to avoid false signals in ranging markets', 'Combines trend strength and direction (DI lines)'],
    limitations: ['Lagging indicator; strong trend may be near exhaustion when ADX finally confirms', 'Complex to interpret for beginners'],
    useCases: ['Trend filter', 'Strategy regime filter', 'Momentum confirmation'],
    tier: 'premium',
    implemented: true,
    difficulty: 'Medium',
    dataRequired: ['Daily OHLCV (minimum 30 days)'],
  },
  {
    id: 'atr',
    name: 'ATR (Average True Range)',
    category: 'Technical',
    description:
      'Measures market volatility by decomposing the range of asset prices. Essential for position sizing and stop-loss placement.',
    formula: 'True Range = max(H-L, |H-Prev Close|, |L-Prev Close|)\nATR = EMA(14) of True Range',
    inputs: ['Daily OHLCV', 'Period (default 14)'],
    measures: 'Typical daily price range; market volatility',
    interpretation:
      'ATR in price units. A stock with ATR = ₹50 typically moves ₹50/day. ATR × 2 is a common stop-loss distance. Normalise as ATR/Price for cross-stock comparison.',
    advantages: ['Price-level appropriate (unlike RSI)', 'Non-directional — pure volatility measure', 'Practical for stop-loss calibration'],
    limitations: ['Does not indicate direction', 'Can spike temporarily on a single event'],
    useCases: ['Stop-loss placement', 'Position sizing', 'Volatility comparison'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Daily OHLCV (minimum 20 days)'],
  },
  {
    id: 'stochastic',
    name: 'Stochastic Oscillator',
    category: 'Technical',
    description:
      'Compares a closing price to its high-low range over a period. Useful for identifying overbought/oversold conditions in ranging markets.',
    formula: '%K = 100 × (Close - Lowest Low(14)) / (Highest High(14) - Lowest Low(14))\n%D = 3-period SMA of %K',
    inputs: ['Daily OHLCV', 'Period (default 14)', 'Smoothing (3)'],
    measures: 'Position of price relative to its range',
    interpretation:
      '%K > 80: overbought (price near top of range). %K < 20: oversold (price near bottom). %K crossing %D is the signal line crossover (similar to MACD signal).',
    advantages: ['Works well in ranging, consolidating markets', 'Bounded 0–100; easy to normalise'],
    limitations: ['Poor in trending markets — generates false signals', 'Sensitive to parameter choice'],
    useCases: ['Mean reversion setups', 'Overbought/oversold detection', 'Entry timing in ranges'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Daily OHLCV (minimum 20 days)'],
  },
  {
    id: 'obv',
    name: 'OBV (On-Balance Volume)',
    category: 'Technical',
    description:
      'Cumulative volume indicator that adds volume on up days and subtracts on down days. Confirms price trends or detects divergences.',
    formula: 'OBV_t = OBV_{t-1} + (Volume if Close > Prev Close, else -Volume)',
    inputs: ['Daily close prices', 'Daily volume'],
    measures: 'Cumulative buying/selling pressure',
    interpretation:
      'OBV rising with price = confirmed uptrend. OBV falling while price rises = bearish divergence (smart money selling into rally). OBV trend is more important than absolute level.',
    advantages: ['Simple and intuitive', 'Leading indicator in some cases (volume precedes price)'],
    limitations: ['Equal-weight volume — a single high-volume anomaly distorts the series', 'Absolute level is not meaningful; only direction matters'],
    useCases: ['Trend confirmation', 'Divergence detection', 'Accumulation/distribution analysis'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Daily close prices and volume'],
  },
  {
    id: 'vwap',
    name: 'VWAP (Volume-Weighted Average Price)',
    category: 'Technical',
    description:
      'Average price weighted by volume. Widely used by institutional traders as an intraday benchmark; the rolling 20-day version is used here for positional analysis.',
    formula: 'VWAP = Σ(Price × Volume) / Σ(Volume)\n(Rolling 20-day window)',
    inputs: ['Daily OHLCV', 'Window (20 days)'],
    measures: 'Fair average price weighted by trading activity',
    interpretation:
      'Price above rolling VWAP = bullish (trading above where most volume transacted recently). Price below = bearish. Institutions often add positions when price dips to VWAP.',
    advantages: ['Volume-informed — more meaningful than simple moving average', 'Used as institutional benchmark'],
    limitations: ['Rolling VWAP (positional) differs from intraday VWAP (reset daily)', 'Less meaningful for illiquid stocks with erratic volume'],
    useCases: ['Entry/exit relative to volume-weighted level', 'Institutional benchmark comparison'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Daily OHLCV'],
  },
  {
    id: 'cci',
    name: 'CCI (Commodity Channel Index)',
    category: 'Technical',
    description:
      'Measures deviation of price from its average price relative to its mean absolute deviation. Originally for commodities but widely applied to equities.',
    formula: 'CCI = (Typical Price - SMA(Typical Price, 20)) / (0.015 × Mean Absolute Deviation)\nTypical Price = (H + L + C) / 3',
    inputs: ['Daily OHLCV', 'Period (default 20)'],
    measures: 'Statistical deviation from average price',
    interpretation:
      'CCI > +100: strong uptrend / overbought. CCI < -100: strong downtrend / oversold. CCI crossing zero from below = bullish signal. Oscillation between ±100 is normal.',
    advantages: ['Unbounded (unlike RSI/Stochastic) — can show extreme readings', 'Responds to both trend and cyclicality'],
    limitations: ['Not standardised across instruments — hard to compare', 'Arbitrary 0.015 constant'],
    useCases: ['Trend strength and direction', 'Overbought/oversold in trending markets'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Daily OHLCV (minimum 30 days)'],
  },
  {
    id: 'parabolic-sar',
    name: 'Parabolic SAR',
    category: 'Technical',
    description:
      'Stop-and-Reverse indicator that places a trailing stop below (bull) or above (bear) price. Generates dynamic stop levels that accelerate as the trend matures.',
    formula: 'Bull: SAR_t = SAR_{t-1} + AF × (EP - SAR_{t-1})\nAF starts at 0.02, increments 0.02 per new extreme, max 0.2\nFlips to bear when price crosses SAR',
    inputs: ['Daily OHLCV', 'Initial AF (0.02)', 'Max AF (0.2)'],
    measures: 'Dynamic trailing stop level and trend direction',
    interpretation:
      'Dots below price = uptrend. Dots above price = downtrend. Price crossing SAR = trend reversal signal. The SAR level is used as a trailing stop-loss.',
    advantages: ['Built-in stop-loss mechanism', 'Trend direction always clear', 'Accelerates stop as trend matures'],
    limitations: ['Performs poorly in ranging/sideways markets — generates many whipsaws', 'Lags at trend turns'],
    useCases: ['Trailing stop placement', 'Trend following', 'Exit signal generation'],
    tier: 'free',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Daily OHLCV (minimum 20 days)'],
  },

  // ─── STRATEGIES (implemented) ─────────────────────────────────
  {
    id: 'ivy-gtaa',
    name: 'Ivy Portfolio / GTAA (Faber 2007)',
    category: 'Strategy',
    description:
      "Mebane Faber's simple trend-following system: hold an asset only if its price is above its N-month moving average, otherwise hold cash. Named for endowment-style asset allocation.",
    formula: 'Signal_i = 1 if Price_i > SMA(N months), else 0\nWeights: equal across assets with Signal = 1\nDefault: MA period = 10 months, monthly rebalance',
    inputs: ['Monthly prices for all assets', 'MA period (default 10 months)', 'Asset universe (NIFTY indices, gold, bonds)'],
    measures: 'Trend filter to avoid large drawdowns while capturing uptrends',
    interpretation:
      'All assets above MA = fully invested. All below = all cash. Portfolio gradually reduces risk as more assets break below their MAs. Historical max drawdown ~20% vs index ~50%.',
    advantages: [
      'Extremely simple — one rule, no optimisation',
      'Dramatically reduces drawdowns vs buy-and-hold',
      'Academically validated across 100+ years of data',
    ],
    limitations: [
      'Whipsaw risk in volatile, trendless markets',
      'Monthly lag — reactive, not predictive',
      'Requires assets with genuine trend persistence',
    ],
    useCases: ['Multi-asset tactical allocation', 'Drawdown reduction', 'Retirement portfolio management'],
    tier: 'premium',
    implemented: true,
    difficulty: 'Low',
    dataRequired: ['Monthly OHLCV for each asset (minimum 18 months)'],
  },
  {
    id: 'cross-sectional-momentum',
    name: 'Cross-Sectional Momentum (Jegadeesh-Titman)',
    category: 'Strategy',
    description:
      "The classic equity momentum strategy (Jegadeesh & Titman, 1993). Rank stocks by 12-month return (skipping the most recent month), buy the top decile, rebalance periodically.",
    formula: 'Momentum Score_i = Return(t-12M to t-1M)\nUniverse: sorted by score descending\nBuy top N (default 10), equal or inverse-vol weighted\nRebalance: monthly or quarterly',
    inputs: ['Monthly close prices for universe', 'Lookback (12 months)', 'Skip period (1 month)', 'Top-N (10)', 'Max position cap (20%)'],
    measures: 'Relative price strength across stocks in a universe',
    interpretation:
      'Top-N stocks (past winners) are held long. Historically the most robust equity factor globally. Skip 1-month reversal effect. Crashes in sharp reversals (2009, 2020).',
    advantages: [
      'One of the best-documented anomalies in finance',
      'Works across global markets and asset classes',
      'Inverse-vol weighting reduces concentration risk',
    ],
    limitations: [
      '"Momentum crashes" — sharp reversals in recovery rallies (March 2020)',
      'Transaction costs erode returns; needs careful cost budgeting',
      'Factor crowding risk as momentum becomes popular',
    ],
    useCases: ['Equity long portfolio', 'Factor allocation', 'Smart-beta strategy'],
    tier: 'premium',
    implemented: true,
    difficulty: 'Medium',
    dataRequired: ['Monthly close prices for stock universe (minimum 15 months)'],
  },

  // ─── COMING SOON: VALUATION ───────────────────────────────────
  {
    id: 'dcf',
    name: 'Discounted Cash Flow (DCF)',
    category: 'Valuation',
    description:
      'Estimates the intrinsic value of a company by discounting projected future free cash flows at the weighted average cost of capital. The gold standard of fundamental valuation.',
    formula: 'Intrinsic Value = Σ FCF_t / (1+WACC)^t + Terminal Value / (1+WACC)^n\nTerminal Value = FCF_n × (1+g) / (WACC - g)',
    inputs: ['Free Cash Flow history', 'Revenue growth rate', 'WACC', 'Terminal growth rate (g)', 'Forecast years (5–10)'],
    measures: 'Present value of all future cash flows',
    interpretation:
      'Intrinsic value > current price → undervalued. Margin of safety (typically 20–30%) applied to account for estimate uncertainty. Highly sensitive to WACC and terminal growth rate.',
    advantages: ['Captures true economic value independent of market sentiment', 'Flexible to model different scenarios'],
    limitations: ['Garbage in, garbage out — highly sensitive to assumptions', 'Free cash flow may be volatile or negative for growth companies'],
    useCases: ['Fundamental stock analysis', 'M&A valuation', 'Long-term investment decisions'],
    tier: 'premium',
    implemented: false,
    difficulty: 'High',
    dataRequired: ['5-year FCF history', 'Balance sheet', 'Income statement', 'Cost of capital estimate'],
  },
  {
    id: 'graham-number',
    name: 'Graham Number',
    category: 'Valuation',
    description:
      "Benjamin Graham's conservative upper limit on stock price based on earnings and book value. A stock trading below its Graham Number is potentially undervalued.",
    formula: 'Graham Number = √(22.5 × EPS × Book Value Per Share)',
    inputs: ['EPS (trailing twelve months)', 'Book Value Per Share'],
    measures: 'Maximum fair price based on earnings and assets',
    interpretation:
      'Price < Graham Number → potentially undervalued by Graham standards. The 22.5 factor = 15 (max P/E) × 1.5 (max P/B). Strict, conservative — works best for stable, mature companies.',
    advantages: ['Simple, robust, requires only 2 inputs', 'Conservative by design — favours safety of margin', 'Works without DCF assumptions'],
    limitations: ['Ignores growth — too conservative for growth stocks', 'Book value is backward-looking (may not reflect intangibles)', 'Not suitable for banks, financial companies'],
    useCases: ['Deep value screening', 'Margin of safety check', 'Value investor shortlist'],
    tier: 'free',
    implemented: false,
    difficulty: 'Low',
    dataRequired: ['EPS (TTM)', 'Book value per share'],
  },
  {
    id: 'epv',
    name: 'Earnings Power Value (EPV)',
    category: 'Valuation',
    description:
      "Bruce Greenwald's no-growth valuation. Values the company assuming current earnings power is maintained in perpetuity — without any growth. Separates value from growth speculation.",
    formula: 'EPV = Adjusted EBIT × (1 - Tax Rate) / WACC\nAdjusted EBIT = Normalised operating earnings (remove cyclical and one-time items)',
    inputs: ['Normalised EBIT', 'Tax rate', 'WACC'],
    measures: 'Value of current earnings if the business never grows',
    interpretation:
      'EPV > Reproduction Value (asset value) → franchise value (moat). EPV vs market price: below = undervalued. If EPV > price but Reproduction Value < price = questionable.',
    advantages: ['Separates growth value from current earnings value', 'Conservative floor valuation', 'Simpler than DCF — no growth forecasting needed'],
    limitations: ['Determining "normalised" earnings requires judgement', 'Misses value of growth optionality for high-growth businesses'],
    useCases: ['Conservative intrinsic value baseline', 'Business quality assessment', 'Moat identification'],
    tier: 'premium',
    implemented: false,
    difficulty: 'Medium',
    dataRequired: ['Income statement (3-5 years)', 'WACC', 'Tax rate'],
  },
  {
    id: 'residual-income',
    name: 'Residual Income Model',
    category: 'Valuation',
    description:
      'Values equity by adding the present value of future residual income (earnings above the cost of equity) to current book value. Popular in accounting-based valuation.',
    formula: 'Intrinsic Value = BV₀ + Σ RI_t / (1+r_e)^t\nRI_t = EPS_t - r_e × BV_{t-1}  (Abnormal earnings)',
    inputs: ['Book value per share', 'ROE forecast', 'Cost of equity (r_e)', 'Forecast years'],
    measures: 'Economic profit (earnings above equity cost) capitalised',
    interpretation:
      'Companies with ROE > Cost of Equity generate positive residual income and trade above book value. Companies destroying economic value (ROE < CoE) trade below book.',
    advantages: ['Incorporates cost of equity directly', 'Avoids reliance on free cash flow (useful for banks)', 'Anchored to observable book value'],
    limitations: ['Requires accurate ROE and cost of equity forecasts', 'Accounting distortions in book value can be significant'],
    useCases: ['Bank and financial firm valuation', 'Excess return analysis', 'Fundamental research'],
    tier: 'premium',
    implemented: false,
    difficulty: 'High',
    dataRequired: ['Book value', 'EPS history', 'ROE', 'Cost of equity'],
  },

  // ─── COMING SOON: QUALITY ─────────────────────────────────────
  {
    id: 'piotroski-f-score',
    name: 'Piotroski F-Score',
    category: 'Quality',
    description:
      'Joseph Piotroski\'s 9-point scoring system for fundamental quality across profitability, leverage, and operating efficiency. Separates financial winners from losers.',
    formula: 'Score = Profitability (4 pts) + Leverage/Liquidity (3 pts) + Operating Efficiency (2 pts)\nRange: 0 (worst) to 9 (best)',
    inputs: ['ROA, CFO, ΔDebt, ΔCurrent ratio, ΔGROSS margin, ΔASSET turnover, Accruals, Share issuance'],
    measures: 'Financial health across 9 binary criteria',
    interpretation:
      'Score 8–9: strong fundamental improvement → buy. Score 0–2: fundamental deterioration → avoid or short. Score 3–7: neutral. Particularly effective combined with value screens.',
    advantages: ['Systematic and objective', 'Proven to identify value traps', 'Works well to screen within a value universe'],
    limitations: ['Backward-looking — uses historical financial data', 'Less useful for loss-making growth companies', 'Annual frequency limits timeliness'],
    useCases: ['Value screen refinement', 'Short-selling candidate identification', 'Quality filter'],
    tier: 'free',
    implemented: false,
    difficulty: 'Medium',
    dataRequired: ['Annual income statement, balance sheet, cash flow statement (2 years)'],
  },
  {
    id: 'altman-z-score',
    name: 'Altman Z-Score',
    category: 'Quality',
    description:
      "Edward Altman's bankruptcy prediction model using 5 financial ratios. Originally developed for manufacturing companies, later adapted for non-manufacturing and emerging markets.",
    formula: 'Z = 1.2X₁ + 1.4X₂ + 3.3X₃ + 0.6X₄ + 1.0X₅\nX₁=Working Capital/Assets, X₂=Retained Earnings/Assets\nX₃=EBIT/Assets, X₄=Market Cap/Total Liabilities, X₅=Sales/Assets',
    inputs: ['Balance sheet (working capital, assets, retained earnings)', 'EBIT', 'Market cap', 'Revenue'],
    measures: 'Probability of financial distress within 2 years',
    interpretation:
      'Z > 2.99: safe zone. 1.81–2.99: grey zone (uncertain). Z < 1.81: distress zone (high bankruptcy risk). Useful as a negative screen — avoid low Z-score stocks.',
    advantages: ['Well-validated over decades', 'Single number for financial health', 'Effective as a negative filter in value screens'],
    limitations: ['Developed on US manufacturing data; less accurate for services, tech, banks', 'Market-cap input makes it partially circular with price'],
    useCases: ['Credit risk assessment', 'Bankruptcy screening', 'Value trap identification'],
    tier: 'premium',
    implemented: false,
    difficulty: 'Medium',
    dataRequired: ['Annual balance sheet', 'Income statement', 'Market capitalisation'],
  },
  {
    id: 'beneish-m-score',
    name: 'Beneish M-Score',
    category: 'Quality',
    description:
      "Messod Beneish's model to detect earnings manipulation. Uses 8 financial ratios to flag companies likely to have inflated reported earnings (caught Enron before it collapsed).",
    formula: 'M = -4.84 + 0.92×DSRI + 0.528×GMI + 0.404×AQI + 0.892×SGI\n    + 0.115×DEPI - 0.172×SGAI + 4.679×TATA - 0.327×LVGI',
    inputs: ['Annual financial statements (balance sheet, income statement, cash flow)'],
    measures: 'Probability of earnings manipulation',
    interpretation:
      'M > -1.78: likely manipulator (red flag). M < -2.22: unlikely manipulator. Between: grey zone. Use as a negative screen — high M-score suggests scrutinise further.',
    advantages: ['Quantitative fraud detection', 'Validated on real manipulation cases', 'Purely fundamental — not priced in quickly'],
    limitations: ['High false positive rate', 'Annual data only', 'Not designed for banks or financial companies'],
    useCases: ['Fraud detection', 'Accounting quality screen', 'Short-selling research'],
    tier: 'premium',
    implemented: false,
    difficulty: 'High',
    dataRequired: ['Two consecutive annual financial statements'],
  },

  // ─── COMING SOON: PROFITABILITY ───────────────────────────────
  {
    id: 'roe',
    name: 'Return on Equity (ROE)',
    category: 'Profitability',
    description:
      "Measures how much profit a company generates with shareholders' equity. Core metric for assessing management effectiveness and business quality.",
    formula: 'ROE = Net Income / Average Shareholders Equity',
    inputs: ['Net income (annual)', "Shareholders' equity (average of beginning and ending year)"],
    measures: 'Profit generation efficiency relative to equity base',
    interpretation:
      'ROE > 15% is generally considered good; > 20% is excellent. Use DuPont decomposition (ROE = Net Margin × Asset Turnover × Leverage) to understand the source.',
    advantages: ['Universal quality metric', 'Comparable across industries', 'DuPont decomposition reveals sources of profitability'],
    limitations: ['High leverage inflates ROE artificially', 'Share buybacks reduce equity and inflate ROE', 'Negative equity makes ROE meaningless'],
    useCases: ['Business quality assessment', 'Sector comparison', 'Quality screening'],
    tier: 'free',
    implemented: false,
    difficulty: 'Low',
    dataRequired: ['Annual income statement', 'Balance sheet'],
  },
  {
    id: 'roic',
    name: 'Return on Invested Capital (ROIC)',
    category: 'Profitability',
    description:
      'Measures how effectively a company uses all its capital (debt + equity) to generate after-tax operating returns. The most comprehensive capital efficiency metric.',
    formula: 'ROIC = NOPAT / Invested Capital\nNOPAT = EBIT × (1 - Tax Rate)\nInvested Capital = Total Equity + Total Debt - Cash',
    inputs: ['EBIT', 'Tax rate', 'Total equity', 'Total debt', 'Cash'],
    measures: 'After-tax operating return on all capital employed',
    interpretation:
      'ROIC > WACC: value creation. ROIC < WACC: value destruction. Sustainable ROIC > 15% over multiple years signals a durable competitive advantage (moat). Compare ROIC to cost of capital.',
    advantages: ['Accounts for both debt and equity', 'Not inflated by leverage (unlike ROE)', 'Best single measure of economic value creation'],
    limitations: ['Goodwill can distort Invested Capital', 'Requires WACC estimation for full interpretation', 'Cyclicals show wide ROIC swings'],
    useCases: ['Moat identification', 'Capital allocation quality', 'Business quality ranking'],
    tier: 'premium',
    implemented: false,
    difficulty: 'Medium',
    dataRequired: ['Annual income statement', 'Balance sheet'],
  },
  {
    id: 'roce',
    name: 'Return on Capital Employed (ROCE)',
    category: 'Profitability',
    description:
      'Measures operating profit relative to capital employed (assets minus current liabilities). Popular in UK markets and for capital-intensive industries.',
    formula: 'ROCE = EBIT / Capital Employed\nCapital Employed = Total Assets - Current Liabilities',
    inputs: ['EBIT', 'Total assets', 'Current liabilities'],
    measures: 'Operating efficiency relative to long-term capital base',
    interpretation:
      'ROCE > 10% is generally acceptable; compare to industry peers. ROCE should ideally exceed the cost of debt. Improving ROCE trend signals operational improvement.',
    advantages: ['Includes long-term debt in capital base', 'Good for capital-intensive sectors (infra, manufacturing)', 'Doesn\'t require equity-only data'],
    limitations: ['EBIT distorted by depreciation policy and asset age', 'Book value of assets may be understated for mature firms'],
    useCases: ['Capital-intensive sector analysis', 'Asset efficiency measurement', 'Trend analysis'],
    tier: 'premium',
    implemented: false,
    difficulty: 'Low',
    dataRequired: ['Annual income statement', 'Balance sheet'],
  },
  {
    id: 'gross-margin',
    name: 'Gross Margin',
    category: 'Profitability',
    description:
      'Revenue minus cost of goods sold as a percentage of revenue. Reflects pricing power, competitive position, and the fundamental economics of the business.',
    formula: 'Gross Margin = (Revenue - COGS) / Revenue × 100%',
    inputs: ['Revenue', 'Cost of Goods Sold'],
    measures: 'Pricing power and production efficiency',
    interpretation:
      'Higher is better and more stable is better. Gross margin > 40% usually signals a software/brand/IP business. < 10% typical for commodity businesses. Declining margin is a red flag.',
    advantages: ['Easy to compute', 'Leading indicator of pricing power and moat', 'Directly comparable within sector'],
    limitations: ['COGS definition varies by company/sector — limits strict comparison', 'Does not account for SG&A or R&D efficiency'],
    useCases: ['Business quality screening', 'Margin trend analysis', 'Peer comparison'],
    tier: 'free',
    implemented: false,
    difficulty: 'Low',
    dataRequired: ['Annual/quarterly income statement'],
  },

  // ─── COMING SOON: VALUE MULTIPLES ────────────────────────────
  {
    id: 'pe-ratio',
    name: 'Price/Earnings (P/E)',
    category: 'Value',
    description:
      'The most widely used valuation multiple. Market price per share divided by earnings per share — how many rupees investors pay per rupee of annual earnings.',
    formula: 'P/E = Market Price Per Share / Earnings Per Share (TTM or Forward)',
    inputs: ['Market price', 'EPS (trailing or forward)'],
    measures: 'Market premium for each unit of earnings',
    interpretation:
      'P/E < 10: potentially cheap (or earnings risk). P/E 15–25: moderate. P/E > 40: priced for high growth. Compare to sector median and historical range. Cyclically adjusted P/E (CAPE) more robust.',
    advantages: ['Universal, widely understood', 'Quick relative valuation', 'Forward P/E incorporates growth expectations'],
    limitations: ['EPS can be manipulated', 'Meaningless for loss-making companies', 'Ignores balance sheet quality'],
    useCases: ['Quick valuation check', 'Sector comparison', 'Relative value screening'],
    tier: 'free',
    implemented: false,
    difficulty: 'Low',
    dataRequired: ['Market cap', 'Net income'],
  },
  {
    id: 'ev-ebitda',
    name: 'EV/EBITDA',
    category: 'Value',
    description:
      "Enterprise Value to EBITDA. Capital-structure-neutral multiple that values the entire business (equity + debt - cash) relative to operating cash earnings. M&A practitioners' preferred metric.",
    formula: 'EV = Market Cap + Total Debt - Cash\nEV/EBITDA = Enterprise Value / EBITDA',
    inputs: ['Market cap', 'Total debt', 'Cash', 'EBITDA'],
    measures: 'Business value relative to operating cash generation',
    interpretation:
      'Lower EV/EBITDA = potentially cheaper. Varies widely by sector: tech SaaS (20–50×), industrials (6–12×), utilities (10–15×). Compare within sector and to historical median.',
    advantages: ['Capital-structure neutral — works across varying leverage levels', 'Less affected by accounting choices than P/E', 'Standard in M&A valuation'],
    limitations: ['EBITDA ignores capex — misleading for capital-intensive industries', 'Does not reflect differences in tax rates across countries'],
    useCases: ['M&A screening', 'Cross-sector comparison (with caution)', 'Leveraged buyout analysis'],
    tier: 'premium',
    implemented: false,
    difficulty: 'Low',
    dataRequired: ['Market cap', 'Total debt', 'Cash', 'EBITDA from income statement'],
  },
  {
    id: 'ev-sales',
    name: 'EV/Sales',
    category: 'Value',
    description:
      'Enterprise Value to revenue. Useful when earnings are negative or highly volatile. Common for early-stage, high-growth companies.',
    formula: 'EV/Sales = Enterprise Value / Annual Revenue',
    inputs: ['Market cap', 'Debt', 'Cash', 'Revenue'],
    measures: 'Price paid per unit of revenue',
    interpretation:
      'EV/Sales < 1: very cheap (may indicate commodity business or distress). EV/Sales 1–5: moderate. > 10: priced for hypergrowth. Compare to growth rate (Price/Sales to Sales Growth).',
    advantages: ['Works for pre-profit companies', 'Revenue harder to manipulate than earnings', 'Useful for high-growth screening'],
    limitations: ['Revenue quality varies — high-revenue, low-margin businesses may look cheap', 'Ignores profitability completely'],
    useCases: ['Early-stage or loss-making company valuation', 'High-growth sector screening'],
    tier: 'free',
    implemented: false,
    difficulty: 'Low',
    dataRequired: ['Market cap', 'Debt', 'Cash', 'Revenue'],
  },
  {
    id: 'price-to-book',
    name: 'Price/Book (P/B)',
    category: 'Value',
    description:
      "Compares market value to accounting book value of equity. The classic Benjamin Graham metric. Still highly relevant for banks, financials, and asset-heavy businesses.",
    formula: 'P/B = Market Price Per Share / Book Value Per Share\nBook Value = Total Equity / Shares Outstanding',
    inputs: ['Market cap', "Total equity (shareholders' equity)"],
    measures: "Market premium over accounting net asset value",
    interpretation:
      "P/B < 1: trading below net assets (deep value or distress). P/B 1–3: normal for most industries. P/B > 5: priced for intangibles/moat. Combine with ROE: high ROE justifies high P/B.",
    advantages: ['Stable metric — book value changes slowly', 'Directly relevant for banks and financial companies', 'Benjamin Graham\'s original value metric'],
    limitations: ['Intangible assets (brands, IP) not on balance sheet in GAAP', 'Goodwill from acquisitions inflates book value', 'Misleading for capital-light businesses'],
    useCases: ['Deep value screening', 'Banking sector valuation', 'Asset-heavy company analysis'],
    tier: 'free',
    implemented: false,
    difficulty: 'Low',
    dataRequired: ['Market cap', 'Total equity'],
  },

  // ─── COMING SOON: GROWTH ──────────────────────────────────────
  {
    id: 'peg-ratio',
    name: 'PEG Ratio',
    category: 'Growth',
    description:
      "Peter Lynch's preferred metric. Adjusts P/E for growth rate — a stock with a P/E of 20 growing at 20% per year has PEG = 1.0 (fairly valued by his rule of thumb).",
    formula: 'PEG = P/E Ratio / Earnings Growth Rate (%)',
    inputs: ['P/E ratio', 'EPS growth rate (1-year forward or 5-year CAGR)'],
    measures: 'Valuation relative to earnings growth',
    interpretation:
      'PEG < 1: potentially undervalued relative to growth. PEG ≈ 1: fairly valued. PEG > 2: growth priced in or overvalued. Peter Lynch considered PEG < 1 a buy signal.',
    advantages: ['Directly adjusts valuation for growth', 'Simple and intuitive', 'Works well for growth at reasonable price (GARP) strategies'],
    limitations: ['Sensitive to which growth rate is used', 'Growth estimates are often inaccurate', 'Breaks down for very high or very low growth rates'],
    useCases: ['GARP (growth at reasonable price) screening', 'Growth company valuation', 'Cross-sector comparison of growth stocks'],
    tier: 'free',
    implemented: false,
    difficulty: 'Low',
    dataRequired: ['EPS (trailing + forward)', 'Market price'],
  },
  {
    id: 'revenue-cagr',
    name: 'Revenue CAGR',
    category: 'Growth',
    description:
      'Compound annual growth rate of revenue over a multi-year period. Measures the organic growth trajectory of a business stripped of one-time items.',
    formula: 'Revenue CAGR = (Revenue_end / Revenue_start)^(1/n) - 1',
    inputs: ['Annual revenue figures', 'Number of years'],
    measures: 'Smoothed revenue growth rate',
    interpretation:
      'Revenue CAGR > 15% is strong for most sectors. Deceleration in CAGR is often a leading indicator of multiple compression. Compare to peers in same sector.',
    advantages: ['Removes year-to-year noise', 'Intuitive and comparable', 'Forward-looking estimates available from analyst consensus'],
    limitations: ['Backward-looking; past growth does not guarantee future growth', 'Inorganic growth (acquisitions) inflates CAGR'],
    useCases: ['Growth quality assessment', 'Revenue trajectory analysis', 'Peer benchmarking'],
    tier: 'free',
    implemented: false,
    difficulty: 'Low',
    dataRequired: ['Annual revenue (3–5 years)'],
  },

  // ─── COMING SOON: MOMENTUM ───────────────────────────────────
  {
    id: 'dual-momentum',
    name: 'Dual Momentum (Gary Antonacci)',
    category: 'Momentum',
    description:
      "Gary Antonacci's combination of absolute momentum (trending above cash) and relative momentum (outperforming other assets). Empirically one of the strongest risk-adjusted return strategies.",
    formula: 'Step 1 (Absolute): If asset return > T-bill return over 12M → eligible\nStep 2 (Relative): Among eligible, pick highest 12M return\nElse: hold T-bills (cash)',
    inputs: ['12-month returns for candidate assets', 'Risk-free rate (T-bill)'],
    measures: 'Trend-filtered cross-asset momentum',
    interpretation:
      'Dual momentum reduces exposure during bear markets (absolute filter) and concentrates in the best-performing asset (relative filter). Classic implementation: US equity vs International equity vs Bonds.',
    advantages: ['Avoids large drawdowns via absolute momentum filter', 'Simple, rule-based, low turnover', 'Decades of validated performance across asset classes'],
    limitations: ['Whipsaw in choppy markets', 'Concentrated — holds only 1–2 assets at a time', 'December-to-January seasonality effects'],
    useCases: ['Asset allocation between equity/bonds', 'Retirement portfolio', 'Tactical multi-asset'],
    tier: 'premium',
    implemented: false,
    difficulty: 'Low',
    dataRequired: ['Monthly returns for 2–3 asset classes (minimum 15 months)'],
  },
  {
    id: '52-week-momentum',
    name: '52-Week Price Momentum',
    category: 'Momentum',
    description:
      'Simple measure of price momentum: 52-week return (or nearness to 52-week high). Empirically predicts short-to-medium term return continuation.',
    formula: '52W Return = (Current Price / Price 52 weeks ago) - 1\n52W High Proximity = Current Price / 52W High',
    inputs: ['Current price', 'Price 52 weeks ago', '52-week high'],
    measures: 'Price strength relative to prior year',
    interpretation:
      '52W proximity > 90% (near 52W high) = strong momentum. 52W return > 20% in top quartile = buy signal. Combine with volume confirmation. Avoid if near 52W low without trend reversal.',
    advantages: ['Simple to compute', 'Widely followed by institutional momentum strategies', '52W high proximity specifically shown to predict returns'],
    limitations: ['Mean reverts — past winners can become losers', 'Earnings or macro events can break momentum abruptly'],
    useCases: ['Momentum screening', 'Trend following filter', 'Breakout identification'],
    tier: 'free',
    implemented: false,
    difficulty: 'Low',
    dataRequired: ['Daily close prices (52 weeks)'],
  },

  // ─── COMING SOON: PORTFOLIO ───────────────────────────────────
  {
    id: 'kelly-criterion',
    name: 'Kelly Criterion',
    category: 'Portfolio',
    description:
      'The mathematically optimal bet/position size that maximises long-run wealth growth rate. Derived from information theory by John Kelly; used by legendary traders and investors.',
    formula: 'f* = (p × b - q) / b\nwhere p = win probability, q = 1-p, b = win/loss ratio\nFor continuous returns: f* = μ/σ² (Sharpe-like optimal fraction)',
    inputs: ['Win probability (p)', 'Win/loss ratio (b)', 'OR: expected return μ, variance σ²'],
    measures: 'Optimal capital fraction to risk per trade/position',
    interpretation:
      'Kelly fraction = fraction of capital to deploy. Full Kelly is theoretically optimal but practically too volatile. "Half Kelly" or "quarter Kelly" reduces volatility while sacrificing some growth.',
    advantages: ['Maximises geometric growth rate in the long run', 'Mathematically provable optimality', 'Prevents both over-betting (ruin) and under-betting (suboptimal growth)'],
    limitations: ['Requires accurate probability estimates — errors cause over-betting', 'Full Kelly leads to near-100% drawdowns (need fractional Kelly)', 'Not applicable with fat-tailed return distributions without adjustment'],
    useCases: ['Position sizing for high-conviction trades', 'Bankroll management', 'Trading system design'],
    tier: 'premium',
    implemented: false,
    difficulty: 'Medium',
    dataRequired: ['Win rate and payoff ratio from backtest, or return/variance estimates'],
  },

  // ─── COMING SOON: FACTOR ─────────────────────────────────────
  {
    id: 'low-vol-factor',
    name: 'Low-Volatility Factor',
    category: 'Factor',
    description:
      'The empirical anomaly that lower-volatility stocks tend to deliver superior risk-adjusted returns. Contradicts CAPM (which predicts higher risk → higher return). Often called the "low-risk anomaly."',
    formula: 'Rank stocks by 12-month realised volatility (ascending)\nSelect bottom quartile; equal or inverse-vol weight',
    inputs: ['Daily returns for universe', 'Lookback (12 months)'],
    measures: 'Exposure to the low-volatility equity factor',
    interpretation:
      'Defensive strategy — tends to outperform in bear markets and underperform in strong bull markets. Beta typically 0.5–0.7. Often combined with value or quality factors.',
    advantages: ['Structural anomaly persisting for 50+ years globally', 'Defensive — reduces drawdowns', 'Works especially well in India and other emerging markets'],
    limitations: ['Underperforms in strong bull markets', 'Factor crowding risk (low-vol ETFs widespread)', 'High sector concentration (utilities, consumer staples)'],
    useCases: ['Risk-minimising equity allocation', 'Smart beta portfolio construction', 'Defensive factor exposure'],
    tier: 'premium',
    implemented: false,
    difficulty: 'Medium',
    dataRequired: ['Daily close prices for universe (minimum 252 days)'],
  },
  {
    id: 'quality-factor',
    name: 'Quality Factor',
    category: 'Factor',
    description:
      'Systematic exposure to high-profitability, low-leverage, stable-earnings businesses. The "defensive" leg of the quality-value-momentum trifecta popularised by AQR and others.',
    formula: 'Quality Score = Z-score average of:\n  ROE, Gross Profit/Assets (Novy-Marx),\n  Earnings stability, Low accruals, Low leverage',
    inputs: ['Financial statements (ROE, GP, accruals, debt)', 'Return history'],
    measures: 'Composite fundamental quality across profitability, safety, and earnings quality',
    interpretation:
      'Top quintile quality stocks — high, stable ROE with low accruals — tend to outperform over 3–5 year horizons. Combine with value to avoid overpaying for quality.',
    advantages: ['Persistent factor globally', 'Low turnover — fundamental data changes slowly', 'Defensive — quality businesses hold up in recessions'],
    limitations: ['Can become expensive (quality stocks may be overvalued)', 'Requires comprehensive financial data', 'Multiple definitions of "quality" create confusion'],
    useCases: ['Core equity allocation', 'Factor portfolio construction', 'Sector-neutral quality ranking'],
    tier: 'premium',
    implemented: false,
    difficulty: 'High',
    dataRequired: ['Annual financial statements (balance sheet, income, cash flow)'],
  },
  {
    id: 'value-factor',
    name: 'Value Factor',
    category: 'Factor',
    description:
      'The systematic premium earned by cheap stocks (low price relative to fundamentals). One of the oldest and most studied factors in academic finance (Fama-French 1993).',
    formula: 'Value composite: Z-score of P/B, P/E, EV/EBITDA, EV/Sales (all inverted)\nHML (High Minus Low) P/B: long bottom-third P/B, short top-third P/B',
    inputs: ['Fundamental valuation multiples for universe'],
    measures: 'Systematic exposure to undervalued vs overvalued stocks',
    interpretation:
      'Long cheapest quintile stocks. Value premium has been ~3–5% annualised historically. Has underperformed in growth-dominant cycles (2010–2020) but remains statistically significant over long periods.',
    advantages: ['Well-documented and long history of outperformance', 'Intuitive — buy cheap', 'Low correlation with momentum factor'],
    limitations: ['Prolonged underperformance periods (value traps)', 'Accounting-based metrics may not reflect true economic value', 'Works better combined with quality (avoid value traps)'],
    useCases: ['Systematic value investing', 'Factor portfolio', 'Value + Quality combination'],
    tier: 'premium',
    implemented: false,
    difficulty: 'Medium',
    dataRequired: ['Market data and fundamental financial data for universe'],
  },
  {
    id: 'momentum-factor',
    name: 'Momentum Factor',
    category: 'Factor',
    description:
      'Systematic exposure to recent past winners over losers. The most consistently profitable factor across geographies and asset classes (Asness, Moskowitz, Pedersen, 2013).',
    formula: 'Momentum = 12-month return (skip last month)\nUMD (Up Minus Down): long top third momentum, short bottom third\nApplied cross-sectionally within a universe',
    inputs: ['Monthly returns for universe (minimum 13 months)'],
    measures: 'Systematic exposure to price momentum',
    interpretation:
      'Top-momentum quintile tends to outperform by 5–8% annualised. Works best within sector (neutralise sector bets). Momentum crashes are abrupt — risk management required.',
    advantages: ['Highest Sharpe ratio of all individual factors historically', 'Works in equities, bonds, commodities, forex', 'Diversified when combined with value'],
    limitations: ['"Momentum crashes" in sharp reversals can be severe (-30% in a month)', 'High turnover = high transaction costs', 'Factor crowding increasingly a concern'],
    useCases: ['Trend following', 'Factor portfolio', 'Combining with value for diversification'],
    tier: 'premium',
    implemented: false,
    difficulty: 'Medium',
    dataRequired: ['Monthly close prices for universe (minimum 13 months)'],
  },
  {
    id: 'size-factor',
    name: 'Size Factor (Small-Cap Premium)',
    category: 'Factor',
    description:
      'The empirical tendency for small-cap stocks to outperform large-cap over long periods (Banz, 1981). Now the "SMB" (Small Minus Big) factor in Fama-French models.',
    formula: 'SMB = Average return of small-cap stocks - Average return of large-cap stocks\nSize proxy: market capitalisation (bottom half vs top half of universe)',
    inputs: ['Market capitalisation and returns for universe'],
    measures: 'Systematic exposure to small-cap outperformance',
    interpretation:
      'Small-cap premium historically ~3% annualised, but volatile. Works best in early economic expansion phases. India has a particularly strong small/mid-cap premium in bull cycles.',
    advantages: ['Long historical track record', 'Particularly strong in India (emerging markets)', 'Low correlation with large-cap exposures'],
    limitations: ['Illiquidity risk in small-cap stocks', 'Factor has weakened post-1990 in US; stronger in EM', 'Transaction costs significantly erode the premium'],
    useCases: ['Small-cap allocation tilt', 'Factor portfolio diversification', 'India mid/small-cap universe construction'],
    tier: 'premium',
    implemented: false,
    difficulty: 'Low',
    dataRequired: ['Market cap and return data for broad equity universe'],
  },
]

export const CATEGORIES: Category[] = [
  'Valuation', 'Quality', 'Profitability', 'Value', 'Growth',
  'Risk', 'Momentum', 'Portfolio', 'Factor', 'Volatility',
  'Technical', 'ML / Regime', 'Strategy',
]

export default catalog
