import SwiftUI

struct ConsentModal: View {
    @Binding var accepted: Bool
    @Environment(\ .dismiss) var dismiss
    
    var body: some View {
        VStack(spacing: 18) {
            Image(systemName: "shield.fill")
                .font(.system(size: 48))
                .foregroundColor(.orange)
            Text("Reference Information")
                .font(.title2.bold())
            Text("This app provides automated reference information from public databases (FDA, NIH, openFDA, SUPP.AI). It is NOT a diagnosis, treatment, or prescription tool.")
                .font(.body)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            
            VStack(alignment: .leading, spacing: 8) {
                Text("FDA Statement (verbatim):")
                    .font(.subheadline.bold())
                Text("\"This statement has not been evaluated by the Food and Drug Administration. This product is not intended to diagnose, treat, cure, or prevent any disease.\"")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(10)
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                
                Text("Supplementary: Information above is an automated reference from public databases — not medical advice. Consult a licensed physician or pharmacist.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal)
            
            Toggle("I understand this is reference information only, not medical advice.", isOn: $accepted)
                .font(.body)
                .padding(.horizontal)
            
            Button("Continue") {
                dismiss()
            }
            .font(.headline)
            .padding(.horizontal, 24)
            .padding(.vertical, 10)
            .background(accepted ? Color.teal : Color.gray)
            .foregroundColor(.white)
            .cornerRadius(10)
            .disabled(!accepted)
        }
        .padding()
        .presentationDetents([.large])
    }
}
