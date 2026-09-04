import SwiftUI
import AVFoundation
import Vision

struct BarcodeScannerView: View {
    @State private var session = AVCaptureSession()
    @State private var previewLayer: AVCaptureVideoPreviewLayer?
    @State private var foundBarcode: String = ""
    
    var body: some View {
        ZStack {
            CameraPreview(session: session)
                .ignoresSafeArea()
            VStack {
                Spacer()
                if !foundBarcode.isEmpty {
                    Text("Barcode: \(foundBarcode)")
                        .font(.headline)
                        .padding()
                        .background(.black.opacity(0.6))
                        .foregroundColor(.white)
                        .cornerRadius(12)
                }
            }
        }
        .onAppear {
            startSession()
        }
    }
    
    func startSession() {
        // P1: integrate AVCaptureDevice + Vision VNDetectBarcodesRequest
        // Local only — no user meds sent
    }
}

struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession
    func makeUIView(context: Context) -> UIView { let v = UIView(); return v }
    func updateUIView(_ uiView: UIView, context: Context) {}
}
