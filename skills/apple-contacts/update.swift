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

let store = CNContactStore()
guard requestAccess(store: store) else {
    fail("{\"error\":\"Contacts access denied. Grant in System Settings > Privacy > Contacts\"}")
}

let keys: [CNKeyDescriptor] = [
    CNContactIdentifierKey as NSString,
    CNContactGivenNameKey as NSString,
    CNContactFamilyNameKey as NSString,
    CNContactOrganizationNameKey as NSString,
    CNContactJobTitleKey as NSString,
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

    if let firstName = stringParam(params, "first_name") {
        contact.givenName = firstName
    }
    if let lastName = stringParam(params, "last_name") {
        contact.familyName = lastName
    }
    if let organization = stringParam(params, "organization") {
        contact.organizationName = organization
    }
    if let jobTitle = stringParam(params, "job_title") {
        contact.jobTitle = jobTitle
    }

    let request = CNSaveRequest()
    request.update(contact)
    try store.execute(request)

    let result: [String: Any] = [
        "id": contact.identifier,
        "status": "updated",
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
