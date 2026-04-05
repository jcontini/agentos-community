"""Auto-generated TypedDict classes from shape YAML — do not edit.

Generated from 78 shapes.
Regenerate with: python generate.py --lang python
"""

from __future__ import annotations

from typing import Any, TypedDict

class Account(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    accountId: str
    accountType: str
    available: float
    balance: float
    bio: str
    cardType: str
    color: str
    creditLimit: float
    displayName: str
    email: str
    handle: str
    identifier: str
    isActive: bool
    issuer: str
    joinedDate: str
    karma: int
    last4: str
    lastActive: str
    minimumPayment: float
    paymentDueDate: str
    phone: str
    followers: list[Account]
    follows: list[Account]
    owner: Person
    platform: Product


class Activity(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    action: str
    changedKeys: list[str]
    duration: float
    published: str
    success: bool
    toolName: str
    folder: Folder
    session: Session


class Actor(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    actorType: str


class Agent(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    actorType: str
    model: str
    provider: str
    sessionId: str


class Aircraft(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    aisle: str
    availability: str
    barcode: str
    calories: float
    categories: list[str]
    currency: str
    department: str
    iataCode: str
    icaoCode: str
    images: Any
    model: str
    novaGroup: int
    nutritionScore: str
    originalPrice: str
    originalPriceAmount: float
    price: str
    priceAmount: float
    prime: bool
    quantity: int
    rangeKm: int
    rating: float
    ratingsCount: int
    reviewCount: int
    seatCapacity: int
    servingSize: str
    sku: str
    soldByWeight: bool
    sponsored: bool
    variant: str
    weight: str
    weightUnit: str
    weightValue: float
    brand: Brand
    manufacturer: Organization
    tagged: list[Tag]


class Airline(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    actorType: str
    alliance: str
    callsign: str
    country: str
    employeeCount: int
    founded: str
    iataCode: str
    icaoCode: str
    industry: str
    domain: Domain
    headquarters: Place
    member: list[Person]
    website: Website


class Airport(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    city: str
    country: str
    countryCode: str
    elevationFt: int
    iataCode: str
    icaoCode: str
    terminalCount: int
    timezone: str
    location: Place
    operator: Organization


class AnalyticsEvent(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    currentUrl: str
    distinctId: str
    properties: Any
    person: Person


class Article(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    language: str
    readingTime: int
    section: str
    wordCount: int
    publishedIn: Website
    publisher: Organization


class Author(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    averageRating: float
    birthDate: str
    followersCount: int
    location: str
    memberSince: str
    twitter: str
    website: str
    worksCount: int
    books: list[Book]


class Book(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    aisle: str
    availability: str
    averageRating: float
    awardsWon: list[str]
    barcode: str
    calories: float
    categories: list[str]
    characters: list[str]
    currency: str
    currentlyReadingCount: int
    dateAdded: str
    dateRead: str
    dateStarted: str
    department: str
    format: str
    genres: list[str]
    images: Any
    isbn: str
    isbn13: str
    language: str
    novaGroup: int
    nutritionScore: str
    originalPrice: str
    originalPriceAmount: float
    originalTitle: str
    pages: int
    places: list[str]
    price: str
    priceAmount: float
    prime: bool
    quantity: int
    rating: float
    ratingsCount: int
    reviewCount: int
    series: str
    servingSize: str
    shelf: str
    sku: str
    soldByWeight: bool
    sponsored: bool
    toReadCount: int
    userRating: float
    weight: str
    weightUnit: str
    weightValue: float
    workUrl: str
    brand: Brand
    contributors: list[Author]
    manufacturer: Organization
    publisher: Organization
    tagged: list[Tag]
    writtenBy: Author


class Branch(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    ahead: int
    behind: int
    commit: str
    isCurrent: bool
    isRemote: bool
    upstream: str
    repository: Repository


class Brand(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    country: str
    founded: str
    tagline: str
    ownedBy: Organization
    website: Website


class Calendar(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    accessRole: str
    backgroundColor: str
    calendarId: str
    color: str
    foregroundColor: str
    isPrimary: bool
    isReadonly: bool
    source: str
    timezone: str
    events: list[Event]
    owner: Person


class Channel(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    banner: str
    subscriberCount: int
    platform: Product


class Class(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    activityType: str
    allDay: bool
    capacity: int
    dateUpdated: str
    endDate: str
    eventType: str
    icalUid: str
    isFull: bool
    recurrence: list[str]
    showAs: str
    sourceTitle: str
    sourceUrl: str
    spotsRemaining: int
    startDate: str
    status: str
    timezone: str
    visibility: str
    attachments: list[File]
    creator: Person
    instructor: Person
    involves: list[Person]
    location: Place
    organizer: Person
    platform: Product
    venue: Place


class Community(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    allowCrypto: bool
    memberCount: int
    privacy: str
    subscriberCount: int
    platform: Product


class Conversation(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    accountEmail: str
    historyId: str
    isArchived: bool
    isGroup: bool
    messageCount: int
    unreadCount: int
    message: list[Message]
    participant: list[Account]
    platform: Product


class DnsRecord(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    domain: str
    recordName: str
    recordType: str
    ttl: int
    values: list[str]


class Document(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    abstract: str
    contentType: str
    encoding: str
    filename: str
    format: str
    kind: str
    language: str
    lineCount: int
    mimeType: str
    path: str
    sha: str
    size: int
    tableOfContents: str
    wordCount: int
    attachedTo: Message
    author: Actor
    citedBy: list[Document]
    references: list[Document]
    repository: Repository


class Domain(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    autoRenew: bool
    expiresAt: str
    nameservers: list[str]
    registrar: str
    status: str


class Email(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    accountEmail: str
    attachments: Any
    authResults: str
    bccRaw: str
    bodyHtml: str
    ccRaw: str
    conversationId: str
    deliveredTo: str
    draftId: str
    feedbackId: str
    hasAttachments: bool
    inReplyTo: str
    isAutomated: bool
    isDraft: bool
    isOutgoing: bool
    isSent: bool
    isSpam: bool
    isStarred: bool
    isTrash: bool
    isUnread: bool
    labelIds: list[str]
    listId: str
    mailer: str
    manageSubscription: str
    messageId: str
    precedence: str
    references: str
    replyTo: str
    returnPath: str
    sizeEstimate: int
    subject: str
    toRaw: str
    unsubscribe: str
    unsubscribeOneClick: bool
    bcc: list[Account]
    cc: list[Account]
    ccDomain: list[Domain]
    domain: Domain
    from_: Account  # from
    inConversation: Conversation
    platform: Product
    repliesTo: Message
    tag: list[Tag]
    to: list[Account]
    toDomain: list[Domain]


class Episode(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    durationMs: int
    episodeNumber: int
    seasonNumber: int
    guest: list[Person]
    series: Podcast
    transcribe: Transcript


class Event(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    allDay: bool
    dateUpdated: str
    endDate: str
    eventType: str
    icalUid: str
    recurrence: list[str]
    showAs: str
    sourceTitle: str
    sourceUrl: str
    startDate: str
    status: str
    timezone: str
    visibility: str
    attachments: list[File]
    creator: Person
    involves: list[Person]
    location: Place
    organizer: Person
    platform: Product


class File(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    encoding: str
    filename: str
    format: str
    kind: str
    lineCount: int
    mimeType: str
    path: str
    sha: str
    size: int
    attachedTo: Message
    repository: Repository


class Flight(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    arrivalTime: str
    cabinClass: str
    carbonEmissions: Any
    departureTime: str
    duration: str
    durationMinutes: int
    flightNumber: str
    layoverMinutes: int
    polyline: str
    sequence: int
    stops: int
    trace: Any
    tracePointCount: int
    vehicleType: str
    aircraft: Aircraft
    airline: Airline
    arrivesAt: Airport
    carrier: Organization
    departsFrom: Airport
    destination: Place
    origin: Place
    trip: Trip


class Folder(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    hasReadme: bool
    path: str
    workspaceType: str
    contains: list[File]
    repository: Repository


class GitCommit(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    additions: int
    committedAt: str
    deletions: int
    filesChanged: int
    message: str
    sha: str
    shortHash: str
    author: Account
    committer: Account
    parent: GitCommit
    repository: Repository


class Group(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    category: str
    memberCount: int


class Hardware(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    aisle: str
    availability: str
    barcode: str
    calories: float
    categories: list[str]
    currency: str
    department: str
    images: Any
    modelNumber: str
    novaGroup: int
    nutritionScore: str
    originalPrice: str
    originalPriceAmount: float
    price: str
    priceAmount: float
    prime: bool
    quantity: int
    rating: float
    ratingsCount: int
    reviewCount: int
    serialNumber: str
    servingSize: str
    sku: str
    soldByWeight: bool
    specs: Any
    sponsored: bool
    weight: str
    weightUnit: str
    weightValue: float
    brand: Brand
    manufacturer: Organization
    tagged: list[Tag]


class Highlight(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    color: str
    position: str
    createdBy: Person
    extractedFrom: Book


class Image(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    altText: str
    appName: str
    displayId: int
    displayIndex: int
    encoding: str
    filename: str
    format: str
    height: int
    kind: str
    lineCount: int
    mimeType: str
    path: str
    sha: str
    size: int
    width: int
    windowId: int
    attachedTo: Message
    repository: Repository


class Leg(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    arrivalTime: str
    cabinClass: str
    carbonEmissions: Any
    departureTime: str
    duration: str
    durationMinutes: int
    flightNumber: str
    layoverMinutes: int
    polyline: str
    sequence: int
    trace: Any
    tracePointCount: int
    vehicleType: str
    aircraft: Aircraft
    carrier: Organization
    destination: Place
    origin: Place
    trip: Trip


class List(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    isDefault: bool
    isPublic: bool
    itemCount: int
    items: Any
    listId: str
    listType: str
    privacy: str
    belongsTo: Account
    contains: list[Product]
    platform: Product


class LoadedModel(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    digest: str
    expiresAt: str
    quantization: str
    size: str
    sizeVram: int
    vramUsage: str


class Meeting(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    allDay: bool
    calendarLink: str
    conferenceProvider: str
    dateUpdated: str
    endDate: str
    eventType: str
    icalUid: str
    isVirtual: bool
    meetingUrl: str
    phoneDialIn: str
    recurrence: list[str]
    showAs: str
    sourceTitle: str
    sourceUrl: str
    startDate: str
    status: str
    timezone: str
    visibility: str
    attachments: list[File]
    creator: Person
    involves: list[Person]
    location: Place
    organizer: Person
    platform: Product
    transcribe: Transcript


class Message(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    conversationId: str
    isOutgoing: bool
    isStarred: bool
    from_: Account  # from
    inConversation: Conversation
    platform: Product
    repliesTo: Message


class Model(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    contextLength: int
    contextWindow: int
    digest: str
    family: str
    format: str
    maxOutput: int
    modality: list[str]
    modelType: str
    parameterSize: str
    pricingInput: str
    pricingOutput: str
    provider: str
    quantization: str
    quantizationLevel: str
    size: str


class Note(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    isPinned: bool
    noteType: str
    createdBy: Person
    extractedFrom: Webpage
    references: list[Note]


class Offer(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    availability: str
    bookingToken: str
    currency: str
    offerType: str
    price: float
    validFrom: str
    validUntil: str
    for_: Product  # for
    offeredBy: Organization
    trips: list[Trip]


class Order(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    currency: str
    deliveryDate: str
    deliveryFee: float
    eta: str
    fareBreakdown: Any
    orderDate: str
    orderId: str
    originalTotal: str
    originalTotalAmount: float
    savings: float
    status: str
    subtotal: float
    summary: str
    taxes: float
    tipAmount: float
    total: str
    totalAmount: float
    contains: list[Product]
    delivery: Trip
    platform: Platform
    shippingAddress: Place
    store: Place
    tracking: Webpage


class Organization(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    actorType: str
    employeeCount: int
    founded: str
    industry: str
    domain: Domain
    headquarters: Place
    member: list[Person]
    website: Website


class Person(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    about: str
    actorType: str
    birthday: str
    firstName: str
    gender: str
    joinedDate: str
    lastActive: str
    lastName: str
    middleName: str
    nickname: str
    notes: str
    accounts: list[Account]
    currentlyReading: list[Book]
    favoriteBooks: list[Book]
    location: Place
    roles: list[Role]
    website: Website


class Place(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    accuracy: str
    businessStatus: str
    categories: list[str]
    city: str
    closedMessage: str
    country: str
    countryCode: str
    district: str
    eta: str
    featureType: str
    fullAddress: str
    googlePlaceId: str
    hours: Any
    isOrderable: bool
    latitude: float
    locality: str
    longitude: float
    mapboxId: str
    neighborhood: str
    phone: str
    placeFormatted: str
    postalCode: str
    priceLevel: str
    productCount: int
    rating: float
    region: str
    reviewCount: int
    street: str
    streetNumber: str
    timezone: str
    website: str
    wikidataId: str
    brand: Organization
    offers: list[Product]


class Platform(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    aisle: str
    availability: str
    barcode: str
    calories: float
    categories: list[str]
    currency: str
    department: str
    images: Any
    license: str
    novaGroup: int
    nutritionScore: str
    openSource: bool
    originalPrice: str
    originalPriceAmount: float
    platform: list[str]
    platformType: str
    price: str
    priceAmount: float
    prime: bool
    quantity: int
    rating: float
    ratingsCount: int
    repositoryUrl: str
    reviewCount: int
    servingSize: str
    sku: str
    soldByWeight: bool
    sponsored: bool
    version: str
    website: str
    weight: str
    weightUnit: str
    weightValue: float
    brand: Brand
    developer: Organization
    manufacturer: Organization
    repository: Repository
    tagged: list[Tag]


class Playlist(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    isDefault: bool
    isPublic: bool
    itemCount: int
    items: Any
    listId: str
    listType: str
    privacy: str
    belongsTo: Account
    contains: list[Video]
    platform: Product


class Podcast(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    feedUrl: str
    episode: list[Episode]
    host: list[Person]
    platform: Product


class Post(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    commentCount: int
    externalUrl: str
    likes: int
    postType: str
    score: int
    viewCount: int
    attachment: list[File]
    contains: list[Video]
    media: list[Image]
    postedBy: Account
    publish: Community
    replies: list[Post]
    repliesTo: Post


class Product(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    aisle: str
    availability: str
    barcode: str
    calories: float
    categories: list[str]
    currency: str
    department: str
    images: Any
    novaGroup: int
    nutritionScore: str
    originalPrice: str
    originalPriceAmount: float
    price: str
    priceAmount: float
    prime: bool
    quantity: int
    rating: float
    ratingsCount: int
    reviewCount: int
    servingSize: str
    sku: str
    soldByWeight: bool
    sponsored: bool
    weight: str
    weightUnit: str
    weightValue: float
    brand: Brand
    manufacturer: Organization
    tagged: list[Tag]


class Project(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    color: str
    state: str


class Quote(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    context: str
    year: int


class Report(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    abstract: str
    confidence: float
    contentType: str
    dataSources: list[str]
    encoding: str
    filename: str
    findings: str
    format: str
    kind: str
    language: str
    lineCount: int
    methodology: str
    mimeType: str
    path: str
    recommendations: str
    reportType: str
    sha: str
    size: int
    subjectId: str
    tableOfContents: str
    wordCount: int
    attachedTo: Message
    author: Actor
    citedBy: list[Document]
    commissionedBy: Actor
    references: list[Document]
    relatedSpecs: list[Spec]
    repository: Repository


class Repository(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    defaultBranch: str
    forks: int
    isArchived: bool
    isPrivate: bool
    language: str
    license: str
    openIssues: int
    size: int
    stars: int
    topics: list[str]
    forkedFrom: Repository
    owner: Account


class Result(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    indexedAt: str
    resultType: str


class Review(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    commentCount: int
    externalUrl: str
    isVerified: bool
    likes: int
    postType: str
    rating: float
    ratingMax: float
    score: int
    tags: list[str]
    viewCount: int
    attachment: list[File]
    contains: list[Video]
    media: list[Image]
    postedBy: Account
    publish: Community
    replies: list[Post]
    repliesTo: Post
    reviews: Product


class Role(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    department: str
    endDate: str
    roleType: str
    startDate: str
    title: str
    organization: Organization
    person: Person


class Route(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    color: str
    cronExpression: str
    direction: str
    durability: str
    enabled: bool
    hours: Any
    lastFiredAt: str
    nextFireAt: str
    prompt: str
    providerJobId: str
    routeNumber: str
    routeType: str
    rrule: str
    scheduleType: str
    timezone: str
    destination: Place
    operator: Organization
    origin: Place
    produces: Trip
    provider: Skill
    stops: list[Place]


class Schedule(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    cronExpression: str
    durability: str
    enabled: bool
    hours: Any
    lastFiredAt: str
    nextFireAt: str
    prompt: str
    providerJobId: str
    rrule: str
    scheduleType: str
    timezone: str
    operator: Organization
    produces: Trip
    provider: Skill


class Search(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    query: str
    resultCount: int
    searchCount: int
    searchedAt: str


class Session(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    client: str
    endedAt: str
    gitBranch: str
    messageCount: int
    projectId: str
    sessionType: str
    startedAt: str
    tokenCount: int
    folder: Folder
    participant: Actor


class Shape(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    also: list[str]
    icon: str
    identity: list[str]
    identity_any: list[str]
    plural: str
    subtitle: str


class Shelf(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    isDefault: bool
    isExclusive: bool
    isPublic: bool
    itemCount: int
    items: Any
    listId: str
    listType: str
    privacy: str
    belongsTo: Account
    contains: list[Book]
    platform: Product


class Shortcut(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    builtin: bool
    filter: str
    target: str
    skill: Skill


class Skill(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    color: str
    description: str
    error: str
    skillId: str
    status: str
    privacyPolicy: Webpage
    termsOfService: Webpage
    website: Website


class Software(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    aisle: str
    availability: str
    barcode: str
    calories: float
    categories: list[str]
    currency: str
    department: str
    images: Any
    license: str
    novaGroup: int
    nutritionScore: str
    openSource: bool
    originalPrice: str
    originalPriceAmount: float
    platform: list[str]
    price: str
    priceAmount: float
    prime: bool
    quantity: int
    rating: float
    ratingsCount: int
    repositoryUrl: str
    reviewCount: int
    servingSize: str
    sku: str
    soldByWeight: bool
    sponsored: bool
    version: str
    weight: str
    weightUnit: str
    weightValue: float
    brand: Brand
    developer: Organization
    manufacturer: Organization
    repository: Repository
    tagged: list[Tag]


class Source(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    address: str
    description: str
    enabled: bool
    lastSynced: str
    platform: str
    sourceId: str
    folder: Folder


class Spec(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    encoding: str
    filename: str
    format: str
    kind: str
    labels: list[str]
    lineCount: int
    mimeType: str
    path: str
    priority: int
    problem: str
    remoteId: str
    sha: str
    size: int
    startedAt: str
    state: str
    successCriteria: str
    targetDate: str
    assignedTo: Person
    attachedTo: Message
    blockedBy: list[Task]
    blocks: list[Task]
    children: list[Task]
    dependsOn: list[Spec]
    parent: Task
    project: Project
    repository: Repository
    supersedes: list[Spec]


class Tag(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    annotated: bool
    color: str
    hash: str
    tagType: str
    repository: Repository


class Task(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    labels: list[str]
    priority: int
    remoteId: str
    startedAt: str
    state: str
    targetDate: str
    assignedTo: Person
    blockedBy: list[Task]
    blocks: list[Task]
    children: list[Task]
    parent: Task
    project: Project
    repository: Repository


class Theme(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    colorScheme: str
    description: str
    family: str
    themeId: str
    wallpaper: Image


class Transaction(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    amount: float
    balance: float
    category: str
    currency: str
    details: Any
    notes: str
    pending: bool
    postingDate: str
    recurring: bool
    type: str
    account: Account


class Transcript(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    contentRole: str
    durationMs: int
    language: str
    segmentCount: int
    segments: Any
    sourceType: str


class Trip(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    arrivalTime: str
    bookingToken: str
    cabinClass: str
    carbonEmissions: Any
    currency: str
    departureTime: str
    distance: str
    duration: str
    durationMinutes: int
    fare: str
    fareAmount: float
    isScheduled: bool
    isSurge: bool
    rating: str
    status: str
    stops: int
    trackingUrl: str
    tripType: str
    vehicleType: str
    carrier: Organization
    destination: Place
    driver: Person
    legs: list[Leg]
    order: Order
    origin: Place


class Vehicle(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    aisle: str
    availability: str
    barcode: str
    bodyType: str
    calories: float
    categories: list[str]
    color: str
    currency: str
    department: str
    drivetrain: str
    fuelType: str
    images: Any
    model: str
    novaGroup: int
    nutritionScore: str
    odometer: int
    originalPrice: str
    originalPriceAmount: float
    price: str
    priceAmount: float
    prime: bool
    quantity: int
    rating: float
    ratingsCount: int
    reviewCount: int
    servingSize: str
    sku: str
    soldByWeight: bool
    sponsored: bool
    transmission: str
    trim: str
    vin: str
    weight: str
    weightUnit: str
    weightValue: float
    year: int
    brand: Brand
    manufacturer: Organization
    tagged: list[Tag]


class Video(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    codec: str
    durationMs: int
    encoding: str
    filename: str
    format: str
    frameRate: float
    kind: str
    lineCount: int
    mimeType: str
    path: str
    resolution: str
    sha: str
    size: int
    addTo: Playlist
    attachedTo: Message
    channel: Channel
    repository: Repository
    transcribe: Transcript


class Volume(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    filesystem: str
    freeBytes: int
    path: str
    readOnly: bool
    removable: bool
    totalBytes: int
    usedBytes: int
    volumeType: str
    contains: list[Folder]


class Webpage(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    contentType: str
    error: str
    lastVisitUnix: int
    visitCount: int


class Website(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    anonymous: bool
    claimToken: str
    claimUrl: str
    expiresAt: str
    status: str
    versionId: str
    domain: Domain
    ownedBy: Organization

