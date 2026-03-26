"""Auto-generated TypedDict classes from shape YAML — do not edit.

Generated from 56 shapes in shapes/.
Regenerate with: python -m agentos.shapes
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
    account_type: str
    bio: str
    color: str
    display_name: str
    email: str
    handle: str
    is_active: bool
    joined_date: str
    karma: int
    last_active: str
    phone: str
    followers: list[Account]
    follows: list[Account]
    owner: Person
    platform: Product


class Actor(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    actor_type: str


class Agent(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    actor_type: str
    model: str
    provider: str
    session_id: str


class Aircraft(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    availability: str
    categories: list[str]
    currency: str
    iata_code: str
    icao_code: str
    images: Any
    model: str
    price: str
    price_amount: float
    prime: bool
    quantity: int
    range_km: int
    rating: float
    ratings_count: int
    review_count: int
    seat_capacity: int
    sponsored: bool
    variant: str
    brand: Brand
    manufacturer: Organization


class Airline(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    actor_type: str
    alliance: str
    callsign: str
    country: str
    employee_count: int
    founded: str
    iata_code: str
    icao_code: str
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
    country_code: str
    elevation_ft: int
    iata_code: str
    icao_code: str
    terminal_count: int
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
    current_url: str
    distinct_id: str
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
    reading_time: int
    section: str
    word_count: int
    published_in: Website
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
    average_rating: float
    birth_date: str
    followers_count: int
    location: str
    member_since: str
    twitter: str
    website: str
    works_count: int
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
    availability: str
    average_rating: float
    awards_won: list[str]
    categories: list[str]
    characters: list[str]
    currency: str
    currently_reading_count: int
    date_added: str
    date_read: str
    date_started: str
    format: str
    genres: list[str]
    images: Any
    isbn: str
    isbn13: str
    language: str
    original_title: str
    pages: int
    places: list[str]
    price: str
    price_amount: float
    prime: bool
    quantity: int
    rating: float
    ratings_count: int
    review_count: int
    series: str
    shelf: str
    sponsored: bool
    to_read_count: int
    user_rating: float
    work_url: str
    brand: Brand
    contributors: list[Author]
    manufacturer: Organization
    publisher: Organization
    written_by: Author


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
    owned_by: Organization
    website: Website


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
    subscriber_count: int
    platform: Product


class Community(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    allow_crypto: bool
    member_count: int
    privacy: str
    subscriber_count: int
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
    account_email: str
    is_archived: bool
    is_group: bool
    unread_count: int
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
    record_name: str
    record_type: str
    ttl: int
    values: list[str]


class Domain(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    auto_renew: bool
    expires_at: str
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
    account_email: str
    attachments: Any
    bcc_raw: str
    body_html: str
    cc_raw: str
    conversation_id: str
    delivered_to: str
    has_attachments: bool
    in_reply_to: str
    is_draft: bool
    is_outgoing: bool
    is_sent: bool
    is_spam: bool
    is_starred: bool
    is_trash: bool
    is_unread: bool
    label_ids: list[str]
    message_id: str
    references: str
    reply_to: str
    size_estimate: int
    subject: str
    to_raw: str
    bcc: list[Account]
    cc: list[Account]
    cc_domain: list[Domain]
    domain: Domain
    from_: Account  # from
    in_conversation: Conversation
    platform: Product
    replies_to: Message
    to: list[Account]
    to_domain: list[Domain]


class Episode(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    duration_ms: int
    episode_number: int
    season_number: int
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
    confidence: str
    details: Any
    end_date: str
    event_date: str
    event_type: str
    documents: list[File]
    involves: list[Person]
    location: Place


class File(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    filename: str
    format: str
    mime_type: str
    path: str
    size: int
    attached_to: Message


class Flight(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    arrival_time: str
    cabin_class: str
    carbon_emissions: Any
    departure_time: str
    duration_minutes: int
    flight_number: str
    stops: int
    aircraft: Aircraft
    airline: Airline
    arrives_at: Airport
    departs_from: Airport
    layovers: list[Airport]


class Folder(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    has_readme: bool
    path: str
    workspace_type: str
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
    committed_at: str
    deletions: int
    files_changed: int
    message: str
    sha: str
    author: Account
    committer: Account
    parent: GitCommit
    repository: Repository


class Hardware(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    availability: str
    categories: list[str]
    currency: str
    images: Any
    model_number: str
    price: str
    price_amount: float
    prime: bool
    quantity: int
    rating: float
    ratings_count: int
    review_count: int
    serial_number: str
    specs: Any
    sponsored: bool
    brand: Brand
    manufacturer: Organization


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
    created_by: Person
    extracted_from: Book


class Image(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    alt_text: str
    filename: str
    format: str
    height: int
    mime_type: str
    path: str
    size: int
    width: int
    attached_to: Message


class List(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    is_default: bool
    is_public: bool
    list_type: str
    privacy: str
    belongs_to: Account
    contains: list[Product]
    platform: Product


class Meeting(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    all_day: bool
    calendar_link: str
    confidence: str
    details: Any
    end_date: str
    event_date: str
    event_type: str
    is_virtual: bool
    meeting_url: str
    recurrence: str
    documents: list[File]
    involves: list[Person]
    location: Place
    organizer: Person
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
    conversation_id: str
    is_outgoing: bool
    from_: Account  # from
    in_conversation: Conversation
    platform: Product
    replies_to: Message


class Note(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    is_pinned: bool
    note_type: str
    created_by: Person
    extracted_from: Webpage
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
    booking_token: str
    currency: str
    offer_type: str
    price: float
    valid_from: str
    valid_until: str
    for_: Product  # for
    offered_by: Organization


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
    delivery_date: str
    status: str
    summary: str
    total: str
    total_amount: float
    contains: list[Product]
    shipping_address: Place
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
    actor_type: str
    employee_count: int
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
    actor_type: str
    birthday: str
    first_name: str
    gender: str
    joined_date: str
    last_active: str
    last_name: str
    middle_name: str
    nickname: str
    notes: str
    accounts: list[Account]
    currently_reading: list[Book]
    favorite_books: list[Book]
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
    city: str
    country: str
    country_code: str
    district: str
    feature_type: str
    full_address: str
    latitude: float
    locality: str
    longitude: float
    mapbox_id: str
    neighborhood: str
    place_formatted: str
    postal_code: str
    region: str
    street: str
    street_number: str
    wikidata_id: str


class Playlist(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    is_default: bool
    is_public: bool
    list_type: str
    privacy: str
    belongs_to: Account
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
    feed_url: str
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
    engagement_comment_count: int  # engagement.comment_count
    engagement_likes: int  # engagement.likes
    engagement_score: int  # engagement.score
    engagement_view_count: int  # engagement.view_count
    external_url: str
    post_type: str
    attachment: list[File]
    contains: list[Video]
    media: list[Image]
    posted_by: Account
    publish: Community
    replies_to: Post


class Product(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    availability: str
    categories: list[str]
    currency: str
    images: Any
    price: str
    price_amount: float
    prime: bool
    quantity: int
    rating: float
    ratings_count: int
    review_count: int
    sponsored: bool
    brand: Brand
    manufacturer: Organization


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
    appears_in: Book
    spoken_by: Person


class Repository(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    default_branch: str
    forks: int
    is_archived: bool
    is_private: bool
    language: str
    license: str
    open_issues: int
    size: int
    stars: int
    topics: list[str]
    forked_from: Repository
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
    indexed_at: str
    result_type: str


class Review(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    engagement_comment_count: int  # engagement.comment_count
    engagement_likes: int  # engagement.likes
    engagement_score: int  # engagement.score
    engagement_view_count: int  # engagement.view_count
    external_url: str
    is_verified: bool
    post_type: str
    rating: float
    rating_max: float
    tags: list[str]
    attachment: list[File]
    contains: list[Video]
    media: list[Image]
    posted_by: Account
    publish: Community
    replies_to: Post
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
    end_date: str
    role_type: str
    start_date: str
    title: str
    organization: Organization
    person: Person


class Session(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    ended_at: str
    message_count: int
    session_type: str
    started_at: str
    token_count: int
    folder: Folder
    participant: Actor
    project: Project


class Shelf(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    is_default: bool
    is_exclusive: bool
    is_public: bool
    list_type: str
    privacy: str
    belongs_to: Account
    contains: list[Book]
    platform: Product


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
    skill_id: str
    status: str
    privacy_policy: Webpage
    terms_of_service: Webpage
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
    availability: str
    categories: list[str]
    currency: str
    images: Any
    license: str
    open_source: bool
    platform: list[str]
    price: str
    price_amount: float
    prime: bool
    quantity: int
    rating: float
    ratings_count: int
    repository_url: str
    review_count: int
    sponsored: bool
    version: str
    brand: Brand
    developer: Organization
    manufacturer: Organization
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
    started_at: str
    state: str
    target_date: str
    assigned_to: Person
    blocked_by: list[Task]
    blocks: list[Task]
    children: list[Task]
    parent: Task
    project: Project
    repository: Repository


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
    posting_date: str
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
    content_role: str
    duration_ms: int
    language: str
    segment_count: int
    segments: Any
    source_type: str


class Vehicle(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    availability: str
    body_type: str
    categories: list[str]
    color: str
    currency: str
    drivetrain: str
    fuel_type: str
    images: Any
    model: str
    odometer: int
    price: str
    price_amount: float
    prime: bool
    quantity: int
    rating: float
    ratings_count: int
    review_count: int
    sponsored: bool
    transmission: str
    trim: str
    vin: str
    year: int
    brand: Brand
    manufacturer: Organization


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
    duration_ms: int
    filename: str
    format: str
    frame_rate: float
    mime_type: str
    path: str
    resolution: str
    size: int
    add_to: Playlist
    attached_to: Message
    channel: Channel
    transcribe: Transcript


class Webpage(TypedDict, total=False):
    id: str
    name: str
    text: str
    url: str
    image: str
    author: str
    datePublished: str
    content: str
    content_type: str
    last_visit_unix: int
    visit_count: int


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
    claim_token: str
    claim_url: str
    expires_at: str
    status: str
    version_id: str
    domain: Domain
    owned_by: Organization

