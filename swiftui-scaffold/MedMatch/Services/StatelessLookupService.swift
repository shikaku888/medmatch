import Foundation
// Stateless lookup — only barcode/ingredient, NEVER user meds/profile
// Endpoint: https://medmatch-api.example.com/api/lookup/{barcode}
// If using local backend for dev: http://localhost:8765/api/lookup/{barcode}

enum LookupError: Error { case network, notFound }

actor StatelessLookupService {
    func lookupBarcode(_ code: String) async throws -> [String: Any] {
    func lookupBarcode(_ code: String) async throws -> [String: Any] {
        guard let url = URL(string: "https://world.openfoodfacts.org/api/v2/product/\(code).json") else { throw LookupError.network }
        let (data, _) = try await URLSession.shared.data(from: url)
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { throw LookupError.notFound }
        return json
    }
    // No cookies, no mt_device, no user profile — stateless
}
