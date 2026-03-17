import Contacts
import Foundation

func fail(_ message: String) -> Never {
    fputs(message + "\n", stderr)
    exit(1)
}

func requestAccess(store: CNContactStore) -> Bool {
    let semaphore = DispatchSemaphore(value: 0)
    var granted = false
    store.requestAccess(for: .contacts) { ok, _ in
        granted = ok
        semaphore.signal()
    }
    semaphore.wait()
    return granted
}

let store = CNContactStore()
guard requestAccess(store: store) else {
    fail("{\"error\":\"Contacts access denied. Grant in System Settings > Privacy > Contacts\"}")
}

do {
    let defaultId = store.defaultContainerIdentifier()
    let containers = try store.containers(matching: nil)
    var results: [[String: Any]] = []

    for container in containers {
        let predicate = CNContact.predicateForContactsInContainer(withIdentifier: container.identifier)
        let count = try store.unifiedContacts(matching: predicate, keysToFetch: []).count
        let dirId = container.identifier.replacingOccurrences(of: ":ABAccount", with: "")
        let defaultDirId = defaultId.replacingOccurrences(of: ":ABAccount", with: "")

        results.append([
            "id": dirId,
            "name": container.name,
            "count": count,
            "is_default": dirId == defaultDirId,
        ])
    }

    let jsonData = try JSONSerialization.data(withJSONObject: results, options: [])
    guard let json = String(data: jsonData, encoding: .utf8) else {
        fail("{\"error\":\"Failed to encode Contacts accounts as UTF-8\"}")
    }
    print(json)
} catch {
    fail("{\"error\":\"\(error.localizedDescription.replacingOccurrences(of: "\"", with: "\\\""))\"}")
}
