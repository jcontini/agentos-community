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

func jsonString(_ value: Any) throws -> String {
    let data = try JSONSerialization.data(withJSONObject: value, options: [])
    guard let string = String(data: data, encoding: .utf8) else {
        throw NSError(domain: "apple-contacts", code: 1, userInfo: [
            NSLocalizedDescriptionKey: "Failed to encode JSON as UTF-8",
        ])
    }
    return string
}

func displayName(for contact: CNContact) -> String {
    let joined = [contact.givenName, contact.familyName]
        .filter { !$0.isEmpty }
        .joined(separator: " ")
    if !joined.isEmpty { return joined }
    if !contact.organizationName.isEmpty { return contact.organizationName }
    return contact.identifier
}

func birthdayString(_ components: DateComponents?) -> String {
    guard let components else { return "" }
    guard let month = components.month, let day = components.day else { return "" }
    let year = components.year ?? 0
    return String(format: "%04d-%02d-%02d", year, month, day)
}

let rawId = CommandLine.arguments.dropFirst().first ?? ""
guard !rawId.isEmpty else {
    fail("{\"error\":\"Missing contact id\"}")
}

let contactId = rawId.hasSuffix(":ABPerson") ? rawId : rawId + ":ABPerson"
let store = CNContactStore()
guard requestAccess(store: store) else {
    fail("{\"error\":\"Contacts access denied. Grant in System Settings > Privacy > Contacts\"}")
}

let keys: [CNKeyDescriptor] = [
    CNContactIdentifierKey as NSString,
    CNContactGivenNameKey as NSString,
    CNContactFamilyNameKey as NSString,
    CNContactMiddleNameKey as NSString,
    CNContactNicknameKey as NSString,
    CNContactOrganizationNameKey as NSString,
    CNContactJobTitleKey as NSString,
    CNContactDepartmentNameKey as NSString,
    CNContactBirthdayKey as NSString,
    CNContactImageDataAvailableKey as NSString,
    CNContactPhoneNumbersKey as NSString,
    CNContactEmailAddressesKey as NSString,
    CNContactUrlAddressesKey as NSString,
    CNContactPostalAddressesKey as NSString,
    CNContactSocialProfilesKey as NSString,
]

do {
    let predicate = CNContact.predicateForContacts(withIdentifiers: [contactId])
    let matches = try store.unifiedContacts(matching: predicate, keysToFetch: keys)
    guard let contact = matches.first else {
        fail("{\"error\":\"Contact not found\"}")
    }

    let phones = contact.phoneNumbers.map { entry in
        [
            "label": entry.label ?? "",
            "value": entry.value.stringValue,
        ]
    }

    let emails = contact.emailAddresses.map { entry in
        [
            "label": entry.label ?? "",
            "value": String(entry.value),
        ]
    }

    let urls = contact.urlAddresses.map { entry in
        [
            "label": entry.label ?? "",
            "url": String(entry.value),
        ]
    }

    let socialProfiles = contact.socialProfiles.compactMap { entry -> [String: String]? in
        let profile = entry.value
        let username = profile.username
        guard !username.isEmpty else { return nil }
        return [
            "service": profile.service,
            "username": username,
        ]
    }

    let addresses = contact.postalAddresses.map { entry in
        let address = entry.value
        return [
            "label": entry.label ?? "",
            "street": address.street,
            "city": address.city,
            "state": address.state,
            "postal_code": address.postalCode,
            "country": address.country,
        ]
    }

    let result: [String: Any] = [
        "id": contact.identifier,
        "first_name": contact.givenName,
        "last_name": contact.familyName,
        "middle_name": contact.middleName,
        "nickname": contact.nickname,
        "display_name": displayName(for: contact),
        "organization": contact.organizationName,
        "job_title": contact.jobTitle,
        "department": contact.departmentName,
        "birthday": birthdayString(contact.birthday),
        // Notes require additional entitlements that we do not have in this helper.
        "notes": "",
        "has_photo": contact.imageDataAvailable ? 1 : 0,
        "phones_json": try jsonString(phones),
        "emails_json": try jsonString(emails),
        "urls_json": try jsonString(urls),
        "social_json": try jsonString(socialProfiles),
        "phones": phones,
        "emails": emails,
        "urls": urls,
        "social_profiles": socialProfiles,
        "addresses": addresses,
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
