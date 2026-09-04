import SwiftUI
import SwiftData

struct ContentView: View {
    @State private var freeScansThisMonth = 5
    @State private var hasPro = false
    @AppStorage("medmatch_first_consent") private var firstConsentAccepted = false
    var canScan: Bool { hasPro || freeScansThisMonth > 0 }
    @Query private var cabinet: [CabinetItem]
    @State private var showScan = false
    
    var body: some View {
        NavigationStack {
            List {
                Section("My Cabinet (local only)") {
                    ForEach(cabinet) { item in
                        HStack {
                            Text(item.name)
                            Spacer()
                            .font(.caption)
                            .foregroundColor(.secondary)
                        }
                    }
                }
                Section("Scan") {
                    Button("Scan Barcode / OCR") { showScan = true }
                }
                Section("Subscription") {
                    NavigationLink("Upgrade — Pro $19/mo • Caregiver $69/mo") { Text("StoreKit 2 screen") }
                }
            }
            .navigationTitle("MedMatch")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Check") { /* engine analyze local cabinet */ }
                }
            }
        }
        .sheet(isPresented: $showScan) { BarcodeScannerView() }
        .sheet(isPresented: .constant(!firstConsentAccepted)) { ConsentModal(accepted: $firstConsentAccepted) } { BarcodeScannerView() }
        .overlay(
            VStack {
                Spacer()
                Text("Reference information only. Not medical advice. FDA disclaimer applies.")
                    .font(.caption2)
                    .padding(8)
                    .frame(maxWidth: .infinity)
                    .background(.black.opacity(0.75))
                    .foregroundColor(.white)
            }
        )
    }
}
