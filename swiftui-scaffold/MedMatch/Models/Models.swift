import Foundation
import SwiftData

@Model
class CabinetItem: Identifiable {
    @Attribute(.unique) var id: UUID = UUID()
    var name: String = ""
    var brand: String = ""
    var kind: String = "supplement" // supplement | drug | food
    var ingredients: String = ""
    var barcode: String = ""
    var addedAt: Date = Date()
    var scheduleHour: Int = 8 // 0-23
    
    init(name: String, brand: String = "", kind: String = "supplement", ingredients: String = "", barcode: String = "", scheduleHour: Int = 8) {
        self.name = name; self.brand = brand; self.kind = kind; self.ingredients = ingredients; self.barcode = barcode; self.scheduleHour = scheduleHour
    }
}

@Model
class InteractionRow: Identifiable {
    @Attribute(.unique) var id: UUID = UUID()
    var itemA: String = ""
    var itemB: String = ""
    var severity: String = "minor" // contraindicated | major | moderate | minor | evidence
    var mechanism: String = ""
    var isInferred: Bool = false // CYP 0.5 — must label NOT verified
    var evidenceDOI: String = ""
    
    init(itemA: String, itemB: String, severity: String, mechanism: String, isInferred: Bool = false, evidenceDOI: String = "") {
        self.itemA = itemA; self.itemB = itemB; self.severity = severity; self.mechanism = mechanism; self.isInferred = isInferred; self.evidenceDOI = evidenceDOI
    }
}

@Model
class ScheduleItem: Identifiable {
    @Attribute(.unique) var id: UUID = UUID()
    var itemName: String = ""
    var timeOfDay: String = "am" // am | pm | both
    var minHoursApart: Int = 2
    
    init(itemName: String, timeOfDay: String = "am", minHoursApart: Int = 2) {
        self.itemName = itemName; self.timeOfDay = timeOfDay; self.minHoursApart = minHoursApart
    }
}
