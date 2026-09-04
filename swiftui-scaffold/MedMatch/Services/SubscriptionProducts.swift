import Foundation
// P1: StoreKit 2 subscription products — Apple handles billing, restore, pricing
// No external Stripe/Web links (ARG 3.1.3)
enum SubscriptionId: String, CaseIterable {
    case proMonthly = "medmatch.pro.monthly"
    case caregiverMonthly = "medmatch.caregiver.monthly"
}

struct SubscriptionInfo {
    static let tiers = [
        (id: SubscriptionId.proMonthly.rawValue, title: "Pro", priceUSD: 19.99, periodMonths: 1, scans: 0), // unlimited
        (id: SubscriptionId.caregiverMonthly.rawValue, title: "Caregiver", priceUSD: 69.99, periodMonths: 1, scans: 0),
    ]
    static let freeScansPerMonth = 5
}
