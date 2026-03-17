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

func arrayParam(_ params: [String: Any], _ key: String) -> [[String: Any]] {
    params[key] as? [[String: Any]] ?? []
}

func labeledPhoneEntries(_ values: [[String: Any]]) -> [CNLabeledValue<CNPhoneNumber>] {
    values.compactMap { item in
        guard let value = item["value"] as? String, !value.isEmpty else { return nil }
        let label = item["label"] as? String
        return CNLabeledValue(label: label, value: CNPhoneNumber(stringValue: value))
    }
}

func labeledEmailEntries(_ values: [[String: Any]]) -> [CNLabeledValue<NSString>] {
    values.compactMap { item in
        guard let value = item["value"] as? String, !value.isEmpty else { return nil }
        let label = item["label"] as? String
        return CNLabeledValue(label: label, value: value as NSString)
    }
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

do {
    let params = try readParams()
    guard let account = stringParam(params, "account") else {
        fail("{\"error\":\"Missing required account\"}")
    }

    let contact = CNMutableContact()
    contact.givenName = stringParam(params, "first_name") ?? ""
    contact.familyName = stringParam(params, "last_name") ?? ""
    contact.organizationName = stringParam(params, "organization") ?? ""
    contact.jobTitle = stringParam(params, "job_title") ?? ""
    contact.phoneNumbers = labeledPhoneEntries(arrayParam(params, "phones"))
    contact.emailAddresses = labeledEmailEntries(arrayParam(params, "emails"))

    let containerId = account.hasSuffix(":ABAccount") ? account : account + ":ABAccount"
    let request = CNSaveRequest()
    request.add(contact, toContainerWithIdentifier: containerId)
    try store.execute(request)

    let result: [String: Any] = [
        "id": contact.identifier,
        "display_name": displayName(for: contact),
        "status": "created",
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
