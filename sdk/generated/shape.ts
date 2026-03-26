// Auto-generated from shape YAML — do not edit.
// Generated from 57 shapes.
// Regenerate with: python generate.py --lang typescript

export interface Account {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    accountType?: string;
    bio?: string;
    color?: string;
    displayName?: string;
    email?: string;
    handle?: string;
    isActive?: boolean;
    joinedDate?: string;
    karma?: number;
    lastActive?: string;
    phone?: string;
    followers?: Account[];
    follows?: Account[];
    owner?: Person;
    platform?: Product;
}

export interface Actor {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    actorType?: string;
}

export interface Agent {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    actorType?: string;
    model?: string;
    provider?: string;
    sessionId?: string;
}

export interface Aircraft {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    availability?: string;
    categories?: string[];
    currency?: string;
    iataCode?: string;
    icaoCode?: string;
    images?: unknown;
    model?: string;
    price?: string;
    priceAmount?: number;
    prime?: boolean;
    quantity?: number;
    rangeKm?: number;
    rating?: number;
    ratingsCount?: number;
    reviewCount?: number;
    seatCapacity?: number;
    sponsored?: boolean;
    variant?: string;
    brand?: Brand;
    manufacturer?: Organization;
}

export interface Airline {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    actorType?: string;
    alliance?: string;
    callsign?: string;
    country?: string;
    employeeCount?: number;
    founded?: string;
    iataCode?: string;
    icaoCode?: string;
    industry?: string;
    domain?: Domain;
    headquarters?: Place;
    member?: Person[];
    website?: Website;
}

export interface Airport {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    city?: string;
    country?: string;
    countryCode?: string;
    elevationFt?: number;
    iataCode?: string;
    icaoCode?: string;
    terminalCount?: number;
    timezone?: string;
    location?: Place;
    operator?: Organization;
}

export interface AnalyticsEvent {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    currentUrl?: string;
    distinctId?: string;
    properties?: unknown;
    person?: Person;
}

export interface Article {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    language?: string;
    readingTime?: number;
    section?: string;
    wordCount?: number;
    publishedIn?: Website;
    publisher?: Organization;
}

export interface Author {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    averageRating?: number;
    birthDate?: string;
    followersCount?: number;
    location?: string;
    memberSince?: string;
    twitter?: string;
    website?: string;
    worksCount?: number;
    books?: Book[];
}

export interface Book {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    availability?: string;
    averageRating?: number;
    awardsWon?: string[];
    categories?: string[];
    characters?: string[];
    currency?: string;
    currentlyReadingCount?: number;
    dateAdded?: string;
    dateRead?: string;
    dateStarted?: string;
    format?: string;
    genres?: string[];
    images?: unknown;
    isbn?: string;
    isbn13?: string;
    language?: string;
    originalTitle?: string;
    pages?: number;
    places?: string[];
    price?: string;
    priceAmount?: number;
    prime?: boolean;
    quantity?: number;
    rating?: number;
    ratingsCount?: number;
    reviewCount?: number;
    series?: string;
    shelf?: string;
    sponsored?: boolean;
    toReadCount?: number;
    userRating?: number;
    workUrl?: string;
    brand?: Brand;
    contributors?: Author[];
    manufacturer?: Organization;
    publisher?: Organization;
    writtenBy?: Author;
}

export interface Brand {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    country?: string;
    founded?: string;
    tagline?: string;
    ownedBy?: Organization;
    website?: Website;
}

export interface Channel {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    banner?: string;
    subscriberCount?: number;
    platform?: Product;
}

export interface Class {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    activityType?: string;
    allDay?: boolean;
    capacity?: number;
    endDate?: string;
    eventType?: string;
    isFull?: boolean;
    recurrence?: string;
    spotsRemaining?: number;
    startDate?: string;
    timezone?: string;
    instructor?: Person;
    involves?: Person[];
    location?: Place;
    organizer?: Person;
    venue?: Place;
}

export interface Community {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    allowCrypto?: boolean;
    memberCount?: number;
    privacy?: string;
    subscriberCount?: number;
    platform?: Product;
}

export interface Conversation {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    accountEmail?: string;
    isArchived?: boolean;
    isGroup?: boolean;
    unreadCount?: number;
    message?: Message[];
    participant?: Account[];
    platform?: Product;
}

export interface DnsRecord {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    domain?: string;
    recordName?: string;
    recordType?: string;
    ttl?: number;
    values?: string[];
}

export interface Domain {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    autoRenew?: boolean;
    expiresAt?: string;
    nameservers?: string[];
    registrar?: string;
    status?: string;
}

export interface Email {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    accountEmail?: string;
    attachments?: unknown;
    bccRaw?: string;
    bodyHtml?: string;
    ccRaw?: string;
    conversationId?: string;
    deliveredTo?: string;
    hasAttachments?: boolean;
    inReplyTo?: string;
    isDraft?: boolean;
    isOutgoing?: boolean;
    isSent?: boolean;
    isSpam?: boolean;
    isStarred?: boolean;
    isTrash?: boolean;
    isUnread?: boolean;
    labelIds?: string[];
    messageId?: string;
    references?: string;
    replyTo?: string;
    sizeEstimate?: number;
    subject?: string;
    toRaw?: string;
    bcc?: Account[];
    cc?: Account[];
    ccDomain?: Domain[];
    domain?: Domain;
    from?: Account;
    inConversation?: Conversation;
    platform?: Product;
    repliesTo?: Message;
    to?: Account[];
    toDomain?: Domain[];
}

export interface Episode {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    durationMs?: number;
    episodeNumber?: number;
    seasonNumber?: number;
    guest?: Person[];
    series?: Podcast;
    transcribe?: Transcript;
}

export interface Event {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    allDay?: boolean;
    endDate?: string;
    eventType?: string;
    recurrence?: string;
    startDate?: string;
    timezone?: string;
    involves?: Person[];
    location?: Place;
    organizer?: Person;
}

export interface File {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    filename?: string;
    format?: string;
    mimeType?: string;
    path?: string;
    size?: number;
    attachedTo?: Message;
}

export interface Flight {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    arrivalTime?: string;
    cabinClass?: string;
    carbonEmissions?: unknown;
    departureTime?: string;
    durationMinutes?: number;
    flightNumber?: string;
    stops?: number;
    aircraft?: Aircraft;
    airline?: Airline;
    arrivesAt?: Airport;
    departsFrom?: Airport;
    layovers?: Airport[];
}

export interface Folder {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    hasReadme?: boolean;
    path?: string;
    workspaceType?: string;
    contains?: File[];
    repository?: Repository;
}

export interface GitCommit {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    additions?: number;
    committedAt?: string;
    deletions?: number;
    filesChanged?: number;
    message?: string;
    sha?: string;
    author?: Account;
    committer?: Account;
    parent?: GitCommit;
    repository?: Repository;
}

export interface Hardware {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    availability?: string;
    categories?: string[];
    currency?: string;
    images?: unknown;
    modelNumber?: string;
    price?: string;
    priceAmount?: number;
    prime?: boolean;
    quantity?: number;
    rating?: number;
    ratingsCount?: number;
    reviewCount?: number;
    serialNumber?: string;
    specs?: unknown;
    sponsored?: boolean;
    brand?: Brand;
    manufacturer?: Organization;
}

export interface Highlight {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    color?: string;
    position?: string;
    createdBy?: Person;
    extractedFrom?: Book;
}

export interface Image {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    altText?: string;
    filename?: string;
    format?: string;
    height?: number;
    mimeType?: string;
    path?: string;
    size?: number;
    width?: number;
    attachedTo?: Message;
}

export interface List {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    isDefault?: boolean;
    isPublic?: boolean;
    listType?: string;
    privacy?: string;
    belongsTo?: Account;
    contains?: Product[];
    platform?: Product;
}

export interface Meeting {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    allDay?: boolean;
    calendarLink?: string;
    endDate?: string;
    eventType?: string;
    isVirtual?: boolean;
    meetingUrl?: string;
    recurrence?: string;
    startDate?: string;
    timezone?: string;
    involves?: Person[];
    location?: Place;
    organizer?: Person;
    transcribe?: Transcript;
}

export interface Message {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    conversationId?: string;
    isOutgoing?: boolean;
    from?: Account;
    inConversation?: Conversation;
    platform?: Product;
    repliesTo?: Message;
}

export interface Note {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    isPinned?: boolean;
    noteType?: string;
    createdBy?: Person;
    extractedFrom?: Webpage;
    references?: Note[];
}

export interface Offer {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    availability?: string;
    bookingToken?: string;
    currency?: string;
    offerType?: string;
    price?: number;
    validFrom?: string;
    validUntil?: string;
    for?: Product;
    offeredBy?: Organization;
}

export interface Order {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    currency?: string;
    deliveryDate?: string;
    status?: string;
    summary?: string;
    total?: string;
    totalAmount?: number;
    contains?: Product[];
    shippingAddress?: Place;
    tracking?: Webpage;
}

export interface Organization {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    actorType?: string;
    employeeCount?: number;
    founded?: string;
    industry?: string;
    domain?: Domain;
    headquarters?: Place;
    member?: Person[];
    website?: Website;
}

export interface Person {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    about?: string;
    actorType?: string;
    birthday?: string;
    firstName?: string;
    gender?: string;
    joinedDate?: string;
    lastActive?: string;
    lastName?: string;
    middleName?: string;
    nickname?: string;
    notes?: string;
    accounts?: Account[];
    currentlyReading?: Book[];
    favoriteBooks?: Book[];
    location?: Place;
    roles?: Role[];
    website?: Website;
}

export interface Place {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    accuracy?: string;
    city?: string;
    country?: string;
    countryCode?: string;
    district?: string;
    featureType?: string;
    fullAddress?: string;
    latitude?: number;
    locality?: string;
    longitude?: number;
    mapboxId?: string;
    neighborhood?: string;
    placeFormatted?: string;
    postalCode?: string;
    region?: string;
    street?: string;
    streetNumber?: string;
    wikidataId?: string;
}

export interface Playlist {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    isDefault?: boolean;
    isPublic?: boolean;
    listType?: string;
    privacy?: string;
    belongsTo?: Account;
    contains?: Video[];
    platform?: Product;
}

export interface Podcast {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    feedUrl?: string;
    episode?: Episode[];
    host?: Person[];
    platform?: Product;
}

export interface Post {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    engagementCommentCount?: number;
    engagementLikes?: number;
    engagementScore?: number;
    engagementViewCount?: number;
    externalUrl?: string;
    postType?: string;
    attachment?: File[];
    contains?: Video[];
    media?: Image[];
    postedBy?: Account;
    publish?: Community;
    repliesTo?: Post;
}

export interface Product {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    availability?: string;
    categories?: string[];
    currency?: string;
    images?: unknown;
    price?: string;
    priceAmount?: number;
    prime?: boolean;
    quantity?: number;
    rating?: number;
    ratingsCount?: number;
    reviewCount?: number;
    sponsored?: boolean;
    brand?: Brand;
    manufacturer?: Organization;
}

export interface Project {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    color?: string;
    state?: string;
}

export interface Quote {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    context?: string;
    appearsIn?: Book;
    spokenBy?: Person;
}

export interface Repository {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    defaultBranch?: string;
    forks?: number;
    isArchived?: boolean;
    isPrivate?: boolean;
    language?: string;
    license?: string;
    openIssues?: number;
    size?: number;
    stars?: number;
    topics?: string[];
    forkedFrom?: Repository;
    owner?: Account;
}

export interface Result {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    indexedAt?: string;
    resultType?: string;
}

export interface Review {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    engagementCommentCount?: number;
    engagementLikes?: number;
    engagementScore?: number;
    engagementViewCount?: number;
    externalUrl?: string;
    isVerified?: boolean;
    postType?: string;
    rating?: number;
    ratingMax?: number;
    tags?: string[];
    attachment?: File[];
    contains?: Video[];
    media?: Image[];
    postedBy?: Account;
    publish?: Community;
    repliesTo?: Post;
    reviews?: Product;
}

export interface Role {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    endDate?: string;
    roleType?: string;
    startDate?: string;
    title?: string;
    organization?: Organization;
    person?: Person;
}

export interface Session {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    endedAt?: string;
    messageCount?: number;
    sessionType?: string;
    startedAt?: string;
    tokenCount?: number;
    folder?: Folder;
    participant?: Actor;
    project?: Project;
}

export interface Shelf {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    isDefault?: boolean;
    isExclusive?: boolean;
    isPublic?: boolean;
    listType?: string;
    privacy?: string;
    belongsTo?: Account;
    contains?: Book[];
    platform?: Product;
}

export interface Skill {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    color?: string;
    description?: string;
    error?: string;
    skillId?: string;
    status?: string;
    privacyPolicy?: Webpage;
    termsOfService?: Webpage;
    website?: Website;
}

export interface Software {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    availability?: string;
    categories?: string[];
    currency?: string;
    images?: unknown;
    license?: string;
    openSource?: boolean;
    platform?: string[];
    price?: string;
    priceAmount?: number;
    prime?: boolean;
    quantity?: number;
    rating?: number;
    ratingsCount?: number;
    repositoryUrl?: string;
    reviewCount?: number;
    sponsored?: boolean;
    version?: string;
    brand?: Brand;
    developer?: Organization;
    manufacturer?: Organization;
    repository?: Repository;
}

export interface Task {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    labels?: string[];
    priority?: number;
    startedAt?: string;
    state?: string;
    targetDate?: string;
    assignedTo?: Person;
    blockedBy?: Task[];
    blocks?: Task[];
    children?: Task[];
    parent?: Task;
    project?: Project;
    repository?: Repository;
}

export interface Transaction {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    amount?: number;
    balance?: number;
    category?: string;
    currency?: string;
    details?: unknown;
    notes?: string;
    pending?: boolean;
    postingDate?: string;
    recurring?: boolean;
    type?: string;
    account?: Account;
}

export interface Transcript {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    contentRole?: string;
    durationMs?: number;
    language?: string;
    segmentCount?: number;
    segments?: unknown;
    sourceType?: string;
}

export interface Vehicle {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    availability?: string;
    bodyType?: string;
    categories?: string[];
    color?: string;
    currency?: string;
    drivetrain?: string;
    fuelType?: string;
    images?: unknown;
    model?: string;
    odometer?: number;
    price?: string;
    priceAmount?: number;
    prime?: boolean;
    quantity?: number;
    rating?: number;
    ratingsCount?: number;
    reviewCount?: number;
    sponsored?: boolean;
    transmission?: string;
    trim?: string;
    vin?: string;
    year?: number;
    brand?: Brand;
    manufacturer?: Organization;
}

export interface Video {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    codec?: string;
    durationMs?: number;
    filename?: string;
    format?: string;
    frameRate?: number;
    mimeType?: string;
    path?: string;
    resolution?: string;
    size?: number;
    addTo?: Playlist;
    attachedTo?: Message;
    channel?: Channel;
    transcribe?: Transcript;
}

export interface Webpage {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    contentType?: string;
    lastVisitUnix?: number;
    visitCount?: number;
}

export interface Website {
    id?: string;
    name?: string;
    text?: string;
    url?: string;
    image?: string;
    author?: string;
    datePublished?: string;
    content?: string;
    anonymous?: boolean;
    claimToken?: string;
    claimUrl?: string;
    expiresAt?: string;
    status?: string;
    versionId?: string;
    domain?: Domain;
    ownedBy?: Organization;
}
