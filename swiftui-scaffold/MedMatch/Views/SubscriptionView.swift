import SwiftUI
import StoreKit

struct SubscriptionView: View {
    @State private var products: [Product] = []
    @State private var purchased = false
    
    init() {
        // P1: fetch products from App Store Connect identifiers
        // Pro $19/mo, Caregiver $69/mo; restore via App Store Settings if needed
    }
    
    var body: some View {
        VStack(spacing: 20) {
            Text("MedMatch Premium")
                .font(.title)
            Text("Free: 5 scans/month\nPro: \$19/month (unlimited)\nCaregiver: \$69/month")
                .multilineTextAlignment(.center)
            Button("Restore Purchases") {
                Task { await AppStore.sync() }
            }
            .buttonStyle(.bordered)
            Text("Subscription auto-renews until canceled in App Store settings.")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .padding()
        .navigationTitle("Subscription")
    }
}
