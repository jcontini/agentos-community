// Auto-generated from shape YAML — do not edit.
// Generated from 57 shapes.
// Regenerate with: python generate.py --lang swift

import Foundation

struct Account: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var accountType: String?
    var bio: String?
    var color: String?
    var displayName: String?
    var email: String?
    var handle: String?
    var isActive: Bool?
    var joinedDate: String?
    var karma: Int?
    var lastActive: String?
    var phone: String?
    var followers: [Account]?
    var follows: [Account]?
    var owner: Person?
    var platform: Product?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, bio, color, email, handle, karma, phone, followers, follows, owner, platform
        case accountType = "account_type"
        case displayName = "display_name"
        case isActive = "is_active"
        case joinedDate = "joined_date"
        case lastActive = "last_active"
    }
}

struct Actor: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var actorType: String?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content
        case actorType = "actor_type"
    }
}

struct Agent: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var actorType: String?
    var model: String?
    var provider: String?
    var sessionId: String?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, model, provider
        case actorType = "actor_type"
        case sessionId = "session_id"
    }
}

struct Aircraft: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var availability: String?
    var categories: [String]?
    var currency: String?
    var iataCode: String?
    var icaoCode: String?
    var images: AnyCodable?
    var model: String?
    var price: String?
    var priceAmount: Double?
    var prime: Bool?
    var quantity: Int?
    var rangeKm: Int?
    var rating: Double?
    var ratingsCount: Int?
    var reviewCount: Int?
    var seatCapacity: Int?
    var sponsored: Bool?
    var variant: String?
    var brand: Brand?
    var manufacturer: Organization?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, availability, categories, currency, images, model, price, prime, quantity, rating, sponsored, variant, brand, manufacturer
        case iataCode = "iata_code"
        case icaoCode = "icao_code"
        case priceAmount = "price_amount"
        case rangeKm = "range_km"
        case ratingsCount = "ratings_count"
        case reviewCount = "review_count"
        case seatCapacity = "seat_capacity"
    }
}

struct Airline: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var actorType: String?
    var alliance: String?
    var callsign: String?
    var country: String?
    var employeeCount: Int?
    var founded: String?
    var iataCode: String?
    var icaoCode: String?
    var industry: String?
    var domain: Domain?
    var headquarters: Place?
    var member: [Person]?
    var website: Website?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, alliance, callsign, country, founded, industry, domain, headquarters, member, website
        case actorType = "actor_type"
        case employeeCount = "employee_count"
        case iataCode = "iata_code"
        case icaoCode = "icao_code"
    }
}

struct Airport: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var city: String?
    var country: String?
    var countryCode: String?
    var elevationFt: Int?
    var iataCode: String?
    var icaoCode: String?
    var terminalCount: Int?
    var timezone: String?
    var location: Place?
    var `operator`: Organization?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, city, country, timezone, location
        case countryCode = "country_code"
        case elevationFt = "elevation_ft"
        case iataCode = "iata_code"
        case icaoCode = "icao_code"
        case terminalCount = "terminal_count"
        case `operator` = "operator"
    }
}

struct AnalyticsEvent: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var currentUrl: String?
    var distinctId: String?
    var properties: AnyCodable?
    var person: Person?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, properties, person
        case currentUrl = "current_url"
        case distinctId = "distinct_id"
    }
}

struct Article: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var language: String?
    var readingTime: Int?
    var section: String?
    var wordCount: Int?
    var publishedIn: Website?
    var publisher: Organization?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, language, section, publisher
        case readingTime = "reading_time"
        case wordCount = "word_count"
        case publishedIn = "published_in"
    }
}

struct Author: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var averageRating: Double?
    var birthDate: String?
    var followersCount: Int?
    var location: String?
    var memberSince: String?
    var twitter: String?
    var website: String?
    var worksCount: Int?
    var books: [Book]?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, location, twitter, website, books
        case averageRating = "average_rating"
        case birthDate = "birth_date"
        case followersCount = "followers_count"
        case memberSince = "member_since"
        case worksCount = "works_count"
    }
}

struct Book: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var availability: String?
    var averageRating: Double?
    var awardsWon: [String]?
    var categories: [String]?
    var characters: [String]?
    var currency: String?
    var currentlyReadingCount: Int?
    var dateAdded: String?
    var dateRead: String?
    var dateStarted: String?
    var format: String?
    var genres: [String]?
    var images: AnyCodable?
    var isbn: String?
    var isbn13: String?
    var language: String?
    var originalTitle: String?
    var pages: Int?
    var places: [String]?
    var price: String?
    var priceAmount: Double?
    var prime: Bool?
    var quantity: Int?
    var rating: Double?
    var ratingsCount: Int?
    var reviewCount: Int?
    var series: String?
    var shelf: String?
    var sponsored: Bool?
    var toReadCount: Int?
    var userRating: Double?
    var workUrl: String?
    var brand: Brand?
    var contributors: [Author]?
    var manufacturer: Organization?
    var publisher: Organization?
    var writtenBy: Author?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, availability, categories, characters, currency, format, genres, images, isbn, isbn13, language, pages, places, price, prime, quantity, rating, series, shelf, sponsored, brand, contributors, manufacturer, publisher
        case averageRating = "average_rating"
        case awardsWon = "awards_won"
        case currentlyReadingCount = "currently_reading_count"
        case dateAdded = "date_added"
        case dateRead = "date_read"
        case dateStarted = "date_started"
        case originalTitle = "original_title"
        case priceAmount = "price_amount"
        case ratingsCount = "ratings_count"
        case reviewCount = "review_count"
        case toReadCount = "to_read_count"
        case userRating = "user_rating"
        case workUrl = "work_url"
        case writtenBy = "written_by"
    }
}

struct Brand: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var country: String?
    var founded: String?
    var tagline: String?
    var ownedBy: Organization?
    var website: Website?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, country, founded, tagline, website
        case ownedBy = "owned_by"
    }
}

struct Channel: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var banner: String?
    var subscriberCount: Int?
    var platform: Product?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, banner, platform
        case subscriberCount = "subscriber_count"
    }
}

struct Class: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var activityType: String?
    var allDay: Bool?
    var capacity: Int?
    var endDate: String?
    var eventType: String?
    var isFull: Bool?
    var recurrence: String?
    var spotsRemaining: Int?
    var startDate: String?
    var timezone: String?
    var instructor: Person?
    var involves: [Person]?
    var location: Place?
    var organizer: Person?
    var venue: Place?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, capacity, recurrence, timezone, instructor, involves, location, organizer, venue
        case activityType = "activity_type"
        case allDay = "all_day"
        case endDate = "end_date"
        case eventType = "event_type"
        case isFull = "is_full"
        case spotsRemaining = "spots_remaining"
        case startDate = "start_date"
    }
}

struct Community: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var allowCrypto: Bool?
    var memberCount: Int?
    var privacy: String?
    var subscriberCount: Int?
    var platform: Product?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, privacy, platform
        case allowCrypto = "allow_crypto"
        case memberCount = "member_count"
        case subscriberCount = "subscriber_count"
    }
}

struct Conversation: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var accountEmail: String?
    var isArchived: Bool?
    var isGroup: Bool?
    var unreadCount: Int?
    var message: [Message]?
    var participant: [Account]?
    var platform: Product?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, message, participant, platform
        case accountEmail = "account_email"
        case isArchived = "is_archived"
        case isGroup = "is_group"
        case unreadCount = "unread_count"
    }
}

struct DnsRecord: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var domain: String?
    var recordName: String?
    var recordType: String?
    var ttl: Int?
    var values: [String]?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, domain, ttl, values
        case recordName = "record_name"
        case recordType = "record_type"
    }
}

struct Domain: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var autoRenew: Bool?
    var expiresAt: String?
    var nameservers: [String]?
    var registrar: String?
    var status: String?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, nameservers, registrar, status
        case autoRenew = "auto_renew"
        case expiresAt = "expires_at"
    }
}

struct Email: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var accountEmail: String?
    var attachments: AnyCodable?
    var bccRaw: String?
    var bodyHtml: String?
    var ccRaw: String?
    var conversationId: String?
    var deliveredTo: String?
    var hasAttachments: Bool?
    var inReplyTo: String?
    var isDraft: Bool?
    var isOutgoing: Bool?
    var isSent: Bool?
    var isSpam: Bool?
    var isStarred: Bool?
    var isTrash: Bool?
    var isUnread: Bool?
    var labelIds: [String]?
    var messageId: String?
    var references: String?
    var replyTo: String?
    var sizeEstimate: Int?
    var subject: String?
    var toRaw: String?
    var bcc: [Account]?
    var cc: [Account]?
    var ccDomain: [Domain]?
    var domain: Domain?
    var from: Account?
    var inConversation: Conversation?
    var platform: Product?
    var repliesTo: Message?
    var to: [Account]?
    var toDomain: [Domain]?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, attachments, references, subject, bcc, cc, domain, from, platform, to
        case accountEmail = "account_email"
        case bccRaw = "bcc_raw"
        case bodyHtml = "body_html"
        case ccRaw = "cc_raw"
        case conversationId = "conversation_id"
        case deliveredTo = "delivered_to"
        case hasAttachments = "has_attachments"
        case inReplyTo = "in_reply_to"
        case isDraft = "is_draft"
        case isOutgoing = "is_outgoing"
        case isSent = "is_sent"
        case isSpam = "is_spam"
        case isStarred = "is_starred"
        case isTrash = "is_trash"
        case isUnread = "is_unread"
        case labelIds = "label_ids"
        case messageId = "message_id"
        case replyTo = "reply_to"
        case sizeEstimate = "size_estimate"
        case toRaw = "to_raw"
        case ccDomain = "cc_domain"
        case inConversation = "in_conversation"
        case repliesTo = "replies_to"
        case toDomain = "to_domain"
    }
}

struct Episode: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var durationMs: Int?
    var episodeNumber: Int?
    var seasonNumber: Int?
    var guest: [Person]?
    var series: Podcast?
    var transcribe: Transcript?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, guest, series, transcribe
        case durationMs = "duration_ms"
        case episodeNumber = "episode_number"
        case seasonNumber = "season_number"
    }
}

struct Event: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var allDay: Bool?
    var endDate: String?
    var eventType: String?
    var recurrence: String?
    var startDate: String?
    var timezone: String?
    var involves: [Person]?
    var location: Place?
    var organizer: Person?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, recurrence, timezone, involves, location, organizer
        case allDay = "all_day"
        case endDate = "end_date"
        case eventType = "event_type"
        case startDate = "start_date"
    }
}

struct File: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var filename: String?
    var format: String?
    var mimeType: String?
    var path: String?
    var size: Int?
    var attachedTo: Message?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, filename, format, path, size
        case mimeType = "mime_type"
        case attachedTo = "attached_to"
    }
}

struct Flight: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var arrivalTime: String?
    var cabinClass: String?
    var carbonEmissions: AnyCodable?
    var departureTime: String?
    var durationMinutes: Int?
    var flightNumber: String?
    var stops: Int?
    var aircraft: Aircraft?
    var airline: Airline?
    var arrivesAt: Airport?
    var departsFrom: Airport?
    var layovers: [Airport]?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, stops, aircraft, airline, layovers
        case arrivalTime = "arrival_time"
        case cabinClass = "cabin_class"
        case carbonEmissions = "carbon_emissions"
        case departureTime = "departure_time"
        case durationMinutes = "duration_minutes"
        case flightNumber = "flight_number"
        case arrivesAt = "arrives_at"
        case departsFrom = "departs_from"
    }
}

struct Folder: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var hasReadme: Bool?
    var path: String?
    var workspaceType: String?
    var contains: [File]?
    var repository: Repository?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, path, contains, repository
        case hasReadme = "has_readme"
        case workspaceType = "workspace_type"
    }
}

struct GitCommit: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var additions: Int?
    var committedAt: String?
    var deletions: Int?
    var filesChanged: Int?
    var message: String?
    var sha: String?
    var author: Account?
    var committer: Account?
    var parent: GitCommit?
    var repository: Repository?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, additions, deletions, message, sha, author, committer, parent, repository
        case committedAt = "committed_at"
        case filesChanged = "files_changed"
    }
}

struct Hardware: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var availability: String?
    var categories: [String]?
    var currency: String?
    var images: AnyCodable?
    var modelNumber: String?
    var price: String?
    var priceAmount: Double?
    var prime: Bool?
    var quantity: Int?
    var rating: Double?
    var ratingsCount: Int?
    var reviewCount: Int?
    var serialNumber: String?
    var specs: AnyCodable?
    var sponsored: Bool?
    var brand: Brand?
    var manufacturer: Organization?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, availability, categories, currency, images, price, prime, quantity, rating, specs, sponsored, brand, manufacturer
        case modelNumber = "model_number"
        case priceAmount = "price_amount"
        case ratingsCount = "ratings_count"
        case reviewCount = "review_count"
        case serialNumber = "serial_number"
    }
}

struct Highlight: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var color: String?
    var position: String?
    var createdBy: Person?
    var extractedFrom: Book?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, color, position
        case createdBy = "created_by"
        case extractedFrom = "extracted_from"
    }
}

struct Image: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var altText: String?
    var filename: String?
    var format: String?
    var height: Int?
    var mimeType: String?
    var path: String?
    var size: Int?
    var width: Int?
    var attachedTo: Message?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, filename, format, height, path, size, width
        case altText = "alt_text"
        case mimeType = "mime_type"
        case attachedTo = "attached_to"
    }
}

struct List: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var isDefault: Bool?
    var isPublic: Bool?
    var listType: String?
    var privacy: String?
    var belongsTo: Account?
    var contains: [Product]?
    var platform: Product?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, privacy, contains, platform
        case isDefault = "is_default"
        case isPublic = "is_public"
        case listType = "list_type"
        case belongsTo = "belongs_to"
    }
}

struct Meeting: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var allDay: Bool?
    var calendarLink: String?
    var endDate: String?
    var eventType: String?
    var isVirtual: Bool?
    var meetingUrl: String?
    var recurrence: String?
    var startDate: String?
    var timezone: String?
    var involves: [Person]?
    var location: Place?
    var organizer: Person?
    var transcribe: Transcript?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, recurrence, timezone, involves, location, organizer, transcribe
        case allDay = "all_day"
        case calendarLink = "calendar_link"
        case endDate = "end_date"
        case eventType = "event_type"
        case isVirtual = "is_virtual"
        case meetingUrl = "meeting_url"
        case startDate = "start_date"
    }
}

struct Message: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var conversationId: String?
    var isOutgoing: Bool?
    var from: Account?
    var inConversation: Conversation?
    var platform: Product?
    var repliesTo: Message?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, from, platform
        case conversationId = "conversation_id"
        case isOutgoing = "is_outgoing"
        case inConversation = "in_conversation"
        case repliesTo = "replies_to"
    }
}

struct Note: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var isPinned: Bool?
    var noteType: String?
    var createdBy: Person?
    var extractedFrom: Webpage?
    var references: [Note]?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, references
        case isPinned = "is_pinned"
        case noteType = "note_type"
        case createdBy = "created_by"
        case extractedFrom = "extracted_from"
    }
}

struct Offer: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var availability: String?
    var bookingToken: String?
    var currency: String?
    var offerType: String?
    var price: Double?
    var validFrom: String?
    var validUntil: String?
    var `for`: Product?
    var offeredBy: Organization?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, availability, currency, price
        case bookingToken = "booking_token"
        case offerType = "offer_type"
        case validFrom = "valid_from"
        case validUntil = "valid_until"
        case `for` = "for"
        case offeredBy = "offered_by"
    }
}

struct Order: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var currency: String?
    var deliveryDate: String?
    var status: String?
    var summary: String?
    var total: String?
    var totalAmount: Double?
    var contains: [Product]?
    var shippingAddress: Place?
    var tracking: Webpage?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, currency, status, summary, total, contains, tracking
        case deliveryDate = "delivery_date"
        case totalAmount = "total_amount"
        case shippingAddress = "shipping_address"
    }
}

struct Organization: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var actorType: String?
    var employeeCount: Int?
    var founded: String?
    var industry: String?
    var domain: Domain?
    var headquarters: Place?
    var member: [Person]?
    var website: Website?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, founded, industry, domain, headquarters, member, website
        case actorType = "actor_type"
        case employeeCount = "employee_count"
    }
}

struct Person: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var about: String?
    var actorType: String?
    var birthday: String?
    var firstName: String?
    var gender: String?
    var joinedDate: String?
    var lastActive: String?
    var lastName: String?
    var middleName: String?
    var nickname: String?
    var notes: String?
    var accounts: [Account]?
    var currentlyReading: [Book]?
    var favoriteBooks: [Book]?
    var location: Place?
    var roles: [Role]?
    var website: Website?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, about, birthday, gender, nickname, notes, accounts, location, roles, website
        case actorType = "actor_type"
        case firstName = "first_name"
        case joinedDate = "joined_date"
        case lastActive = "last_active"
        case lastName = "last_name"
        case middleName = "middle_name"
        case currentlyReading = "currently_reading"
        case favoriteBooks = "favorite_books"
    }
}

struct Place: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var accuracy: String?
    var city: String?
    var country: String?
    var countryCode: String?
    var district: String?
    var featureType: String?
    var fullAddress: String?
    var latitude: Double?
    var locality: String?
    var longitude: Double?
    var mapboxId: String?
    var neighborhood: String?
    var placeFormatted: String?
    var postalCode: String?
    var region: String?
    var street: String?
    var streetNumber: String?
    var wikidataId: String?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, accuracy, city, country, district, latitude, locality, longitude, neighborhood, region, street
        case countryCode = "country_code"
        case featureType = "feature_type"
        case fullAddress = "full_address"
        case mapboxId = "mapbox_id"
        case placeFormatted = "place_formatted"
        case postalCode = "postal_code"
        case streetNumber = "street_number"
        case wikidataId = "wikidata_id"
    }
}

struct Playlist: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var isDefault: Bool?
    var isPublic: Bool?
    var listType: String?
    var privacy: String?
    var belongsTo: Account?
    var contains: [Video]?
    var platform: Product?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, privacy, contains, platform
        case isDefault = "is_default"
        case isPublic = "is_public"
        case listType = "list_type"
        case belongsTo = "belongs_to"
    }
}

struct Podcast: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var feedUrl: String?
    var episode: [Episode]?
    var host: [Person]?
    var platform: Product?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, episode, host, platform
        case feedUrl = "feed_url"
    }
}

struct Post: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var commentCount: Int?
    var externalUrl: String?
    var likes: Int?
    var postType: String?
    var score: Int?
    var viewCount: Int?
    var attachment: [File]?
    var contains: [Video]?
    var media: [Image]?
    var postedBy: Account?
    var publish: Community?
    var repliesTo: Post?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, likes, score, attachment, contains, media, publish
        case commentCount = "comment_count"
        case externalUrl = "external_url"
        case postType = "post_type"
        case viewCount = "view_count"
        case postedBy = "posted_by"
        case repliesTo = "replies_to"
    }
}

struct Product: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var availability: String?
    var categories: [String]?
    var currency: String?
    var images: AnyCodable?
    var price: String?
    var priceAmount: Double?
    var prime: Bool?
    var quantity: Int?
    var rating: Double?
    var ratingsCount: Int?
    var reviewCount: Int?
    var sponsored: Bool?
    var brand: Brand?
    var manufacturer: Organization?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, availability, categories, currency, images, price, prime, quantity, rating, sponsored, brand, manufacturer
        case priceAmount = "price_amount"
        case ratingsCount = "ratings_count"
        case reviewCount = "review_count"
    }
}

struct Project: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var color: String?
    var state: String?
}

struct Quote: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var context: String?
    var appearsIn: Book?
    var spokenBy: Person?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, context
        case appearsIn = "appears_in"
        case spokenBy = "spoken_by"
    }
}

struct Repository: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var defaultBranch: String?
    var forks: Int?
    var isArchived: Bool?
    var isPrivate: Bool?
    var language: String?
    var license: String?
    var openIssues: Int?
    var size: Int?
    var stars: Int?
    var topics: [String]?
    var forkedFrom: Repository?
    var owner: Account?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, forks, language, license, size, stars, topics, owner
        case defaultBranch = "default_branch"
        case isArchived = "is_archived"
        case isPrivate = "is_private"
        case openIssues = "open_issues"
        case forkedFrom = "forked_from"
    }
}

struct Result: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var indexedAt: String?
    var resultType: String?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content
        case indexedAt = "indexed_at"
        case resultType = "result_type"
    }
}

struct Review: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var commentCount: Int?
    var externalUrl: String?
    var isVerified: Bool?
    var likes: Int?
    var postType: String?
    var rating: Double?
    var ratingMax: Double?
    var score: Int?
    var tags: [String]?
    var viewCount: Int?
    var attachment: [File]?
    var contains: [Video]?
    var media: [Image]?
    var postedBy: Account?
    var publish: Community?
    var repliesTo: Post?
    var reviews: Product?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, likes, rating, score, tags, attachment, contains, media, publish, reviews
        case commentCount = "comment_count"
        case externalUrl = "external_url"
        case isVerified = "is_verified"
        case postType = "post_type"
        case ratingMax = "rating_max"
        case viewCount = "view_count"
        case postedBy = "posted_by"
        case repliesTo = "replies_to"
    }
}

struct Role: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var endDate: String?
    var roleType: String?
    var startDate: String?
    var title: String?
    var organization: Organization?
    var person: Person?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, title, organization, person
        case endDate = "end_date"
        case roleType = "role_type"
        case startDate = "start_date"
    }
}

struct Session: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var endedAt: String?
    var messageCount: Int?
    var sessionType: String?
    var startedAt: String?
    var tokenCount: Int?
    var folder: Folder?
    var participant: Actor?
    var project: Project?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, folder, participant, project
        case endedAt = "ended_at"
        case messageCount = "message_count"
        case sessionType = "session_type"
        case startedAt = "started_at"
        case tokenCount = "token_count"
    }
}

struct Shelf: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var isDefault: Bool?
    var isExclusive: Bool?
    var isPublic: Bool?
    var listType: String?
    var privacy: String?
    var belongsTo: Account?
    var contains: [Book]?
    var platform: Product?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, privacy, contains, platform
        case isDefault = "is_default"
        case isExclusive = "is_exclusive"
        case isPublic = "is_public"
        case listType = "list_type"
        case belongsTo = "belongs_to"
    }
}

struct Skill: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var color: String?
    var description: String?
    var error: String?
    var skillId: String?
    var status: String?
    var privacyPolicy: Webpage?
    var termsOfService: Webpage?
    var website: Website?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, color, description, error, status, website
        case skillId = "skill_id"
        case privacyPolicy = "privacy_policy"
        case termsOfService = "terms_of_service"
    }
}

struct Software: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var availability: String?
    var categories: [String]?
    var currency: String?
    var images: AnyCodable?
    var license: String?
    var openSource: Bool?
    var platform: [String]?
    var price: String?
    var priceAmount: Double?
    var prime: Bool?
    var quantity: Int?
    var rating: Double?
    var ratingsCount: Int?
    var repositoryUrl: String?
    var reviewCount: Int?
    var sponsored: Bool?
    var version: String?
    var brand: Brand?
    var developer: Organization?
    var manufacturer: Organization?
    var repository: Repository?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, availability, categories, currency, images, license, platform, price, prime, quantity, rating, sponsored, version, brand, developer, manufacturer, repository
        case openSource = "open_source"
        case priceAmount = "price_amount"
        case ratingsCount = "ratings_count"
        case repositoryUrl = "repository_url"
        case reviewCount = "review_count"
    }
}

struct Task: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var labels: [String]?
    var priority: Int?
    var startedAt: String?
    var state: String?
    var targetDate: String?
    var assignedTo: Person?
    var blockedBy: [Task]?
    var blocks: [Task]?
    var children: [Task]?
    var parent: Task?
    var project: Project?
    var repository: Repository?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, labels, priority, state, blocks, children, parent, project, repository
        case startedAt = "started_at"
        case targetDate = "target_date"
        case assignedTo = "assigned_to"
        case blockedBy = "blocked_by"
    }
}

struct Transaction: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var amount: Double?
    var balance: Double?
    var category: String?
    var currency: String?
    var details: AnyCodable?
    var notes: String?
    var pending: Bool?
    var postingDate: String?
    var recurring: Bool?
    var type: String?
    var account: Account?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, amount, balance, category, currency, details, notes, pending, recurring, type, account
        case postingDate = "posting_date"
    }
}

struct Transcript: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var contentRole: String?
    var durationMs: Int?
    var language: String?
    var segmentCount: Int?
    var segments: AnyCodable?
    var sourceType: String?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, language, segments
        case contentRole = "content_role"
        case durationMs = "duration_ms"
        case segmentCount = "segment_count"
        case sourceType = "source_type"
    }
}

struct Vehicle: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var availability: String?
    var bodyType: String?
    var categories: [String]?
    var color: String?
    var currency: String?
    var drivetrain: String?
    var fuelType: String?
    var images: AnyCodable?
    var model: String?
    var odometer: Int?
    var price: String?
    var priceAmount: Double?
    var prime: Bool?
    var quantity: Int?
    var rating: Double?
    var ratingsCount: Int?
    var reviewCount: Int?
    var sponsored: Bool?
    var transmission: String?
    var trim: String?
    var vin: String?
    var year: Int?
    var brand: Brand?
    var manufacturer: Organization?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, availability, categories, color, currency, drivetrain, images, model, odometer, price, prime, quantity, rating, sponsored, transmission, trim, vin, year, brand, manufacturer
        case bodyType = "body_type"
        case fuelType = "fuel_type"
        case priceAmount = "price_amount"
        case ratingsCount = "ratings_count"
        case reviewCount = "review_count"
    }
}

struct Video: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var codec: String?
    var durationMs: Int?
    var filename: String?
    var format: String?
    var frameRate: Double?
    var mimeType: String?
    var path: String?
    var resolution: String?
    var size: Int?
    var addTo: Playlist?
    var attachedTo: Message?
    var channel: Channel?
    var transcribe: Transcript?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, codec, filename, format, path, resolution, size, channel, transcribe
        case durationMs = "duration_ms"
        case frameRate = "frame_rate"
        case mimeType = "mime_type"
        case addTo = "add_to"
        case attachedTo = "attached_to"
    }
}

struct Webpage: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var contentType: String?
    var lastVisitUnix: Int?
    var visitCount: Int?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content
        case contentType = "content_type"
        case lastVisitUnix = "last_visit_unix"
        case visitCount = "visit_count"
    }
}

struct Website: Codable {
    var id: String?
    var name: String?
    var text: String?
    var url: String?
    var image: String?
    var author: String?
    var datePublished: String?
    var content: String?
    var anonymous: Bool?
    var claimToken: String?
    var claimUrl: String?
    var expiresAt: String?
    var status: String?
    var versionId: String?
    var domain: Domain?
    var ownedBy: Organization?

    enum CodingKeys: String, CodingKey {
        case id, name, text, url, image, author, datePublished, content, anonymous, status, domain
        case claimToken = "claim_token"
        case claimUrl = "claim_url"
        case expiresAt = "expires_at"
        case versionId = "version_id"
        case ownedBy = "owned_by"
    }
}
