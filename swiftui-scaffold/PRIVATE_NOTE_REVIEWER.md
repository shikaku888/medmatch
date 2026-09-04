# Private Note for App Store Reviewer (do NOT publish)
Health reference app under FDA enforcement discretion (information only, not diagnosis/treatment). 
- All medical explanations derived from structured databases (DailyMed, SUPP.AI, openFDA, RxNorm, PubChem); no generative AI claims (Gemini disabled in this build; LLM only polishes existing engine output when enabled, never adds new facts).
- Vietnamese language option removed for US release; primary regulatory text is English per 21 CFR §101.93(c). Supplementary translated line renders next to verbatim FDA statement, never replaces it.
- No clinician verification for CYP-inferred pairs (trust 0.5); clearly labeled "Inferred — not verified by clinician." No pharmacist/dietitian sign-off available; therefore no "pharmacist verified" or "clinical review" claims in marketing.
- User data (medications, interactions, schedule) stored locally via SwiftData; backend is stateless lookup only (barcode/ingredient search via Open Food Facts / PubChem). No server-side PHI storage, no cookie tracking.
- Subscription uses Apple IAP (StoreKit 2); no external payment links. Restore available via App Settings.
- Demonstration video shows scan → reference result → subscription screen; disclaimer visible in every frame.
