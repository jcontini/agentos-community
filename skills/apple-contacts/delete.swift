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

func readParams() throws -> [String: Any] {
    let input = FileHandle.standardInput.readDataToEndOfFile()
    guard !input.isEmpty else { return [:] }
    let value = try JSONSerialization.jsonObject(with: input)
    return value as? [String: Any] ?? [:]
}

func stringParam(_ params: [String: Any], _ key: String) -> String? {
    guard let value = params[key] as? String, !value.isEmpty else { return nil }
    return value
}

func displayName(for contact: CNContact) -> String {
    let joined = [contact.givenName, contact.familyName]
        .filter { !$0.isEmpty }
        .joined(separator: " ")
    if !joined.isEmpty { return joined }
    if !contact.organizationName.isEmpty { return contact.organizationName }
    return contact.identifier
}

let store = CNContactStore()
guard requestAccess(store: store) else {
    fail("{\"error\":\"Contacts access denied. Grant in System Settings > Privacy > Contacts\"}")
}

let keys: [CNKeyDescriptor] = [
    CNContactIdentifierKey as NSString,
    CNContactGivenNameKey as NSString,
    CNContactFamilyNameKey as NSString,
    CNContactOrganizationNameKey as NSString,
]

do {
    let params = try readParams()
    guard let rawId = stringParam(params, "id") else {
        fail("{\"error\":\"Missing required id\"}")
    }
    let contactId = rawId.hasSuffix(":ABPerson") ? rawId : rawId + ":ABPerson"

    let predicate = CNContact.predicateForContacts(withIdentifiers: [contactId])
    let matches = try store.unifiedContacts(matching: predicate, keysToFetch: keys)
    guard let contact = matches.first?.mutableCopy() as? CNMutableContact else {
        fail("{\"error\":\"Contact not found\"}")
    }

    let name = displayName(for: contact)
    let request = CNSaveRequest()
    request.delete(contact)
    try store.execute(request)

    let result: [String: Any] = [
        "status": "deleted",
        "name": name,
    ]
    let data = try JSONSerialization.data(withJSONObject: result, options: [])
    guard let json = String(data: data, encoding: .utf8) else {
        fail("{\"error\":\"Failed to encode contact as UTF-8\"}")
    }
    print(json)
} catch {
    let escaped = error.localizedDescription.replacingOccurrences(of: "\"", with: "\\\"")
    fail("{\"error\":\"\(escaped)\"}")
}
