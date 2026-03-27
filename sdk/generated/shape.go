// Auto-generated from shape YAML — do not edit.
// Generated from 57 shapes.
// Regenerate with: python generate.py --lang go

package shapes

type Account struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	AccountType *string `json:"account_type,omitempty"`
	Bio *string `json:"bio,omitempty"`
	Color *string `json:"color,omitempty"`
	DisplayName *string `json:"display_name,omitempty"`
	Email *string `json:"email,omitempty"`
	Handle *string `json:"handle,omitempty"`
	IsActive *bool `json:"is_active,omitempty"`
	JoinedDate *string `json:"joined_date,omitempty"`
	Karma *int `json:"karma,omitempty"`
	LastActive *string `json:"last_active,omitempty"`
	Phone *string `json:"phone,omitempty"`
	Followers []Account `json:"followers,omitempty"`
	Follows []Account `json:"follows,omitempty"`
	Owner *Person `json:"owner,omitempty"`
	Platform *Product `json:"platform,omitempty"`
}

type Actor struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	ActorType *string `json:"actor_type,omitempty"`
}

type Agent struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	ActorType *string `json:"actor_type,omitempty"`
	Model *string `json:"model,omitempty"`
	Provider *string `json:"provider,omitempty"`
	SessionID *string `json:"session_id,omitempty"`
}

type Aircraft struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Availability *string `json:"availability,omitempty"`
	Categories []string `json:"categories,omitempty"`
	Currency *string `json:"currency,omitempty"`
	IataCode *string `json:"iata_code,omitempty"`
	IcaoCode *string `json:"icao_code,omitempty"`
	Images *any `json:"images,omitempty"`
	Model *string `json:"model,omitempty"`
	Price *string `json:"price,omitempty"`
	PriceAmount *float64 `json:"price_amount,omitempty"`
	Prime *bool `json:"prime,omitempty"`
	Quantity *int `json:"quantity,omitempty"`
	RangeKm *int `json:"range_km,omitempty"`
	Rating *float64 `json:"rating,omitempty"`
	RatingsCount *int `json:"ratings_count,omitempty"`
	ReviewCount *int `json:"review_count,omitempty"`
	SeatCapacity *int `json:"seat_capacity,omitempty"`
	Sponsored *bool `json:"sponsored,omitempty"`
	Variant *string `json:"variant,omitempty"`
	Brand *Brand `json:"brand,omitempty"`
	Manufacturer *Organization `json:"manufacturer,omitempty"`
}

type Airline struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	ActorType *string `json:"actor_type,omitempty"`
	Alliance *string `json:"alliance,omitempty"`
	Callsign *string `json:"callsign,omitempty"`
	Country *string `json:"country,omitempty"`
	EmployeeCount *int `json:"employee_count,omitempty"`
	Founded *string `json:"founded,omitempty"`
	IataCode *string `json:"iata_code,omitempty"`
	IcaoCode *string `json:"icao_code,omitempty"`
	Industry *string `json:"industry,omitempty"`
	Domain *Domain `json:"domain,omitempty"`
	Headquarters *Place `json:"headquarters,omitempty"`
	Member []Person `json:"member,omitempty"`
	Website *Website `json:"website,omitempty"`
}

type Airport struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	City *string `json:"city,omitempty"`
	Country *string `json:"country,omitempty"`
	CountryCode *string `json:"country_code,omitempty"`
	ElevationFt *int `json:"elevation_ft,omitempty"`
	IataCode *string `json:"iata_code,omitempty"`
	IcaoCode *string `json:"icao_code,omitempty"`
	TerminalCount *int `json:"terminal_count,omitempty"`
	Timezone *string `json:"timezone,omitempty"`
	Location *Place `json:"location,omitempty"`
	Operator *Organization `json:"operator,omitempty"`
}

type AnalyticsEvent struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	CurrentURL *string `json:"current_url,omitempty"`
	DistinctID *string `json:"distinct_id,omitempty"`
	Properties *any `json:"properties,omitempty"`
	Person *Person `json:"person,omitempty"`
}

type Article struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Language *string `json:"language,omitempty"`
	ReadingTime *int `json:"reading_time,omitempty"`
	Section *string `json:"section,omitempty"`
	WordCount *int `json:"word_count,omitempty"`
	PublishedIn *Website `json:"published_in,omitempty"`
	Publisher *Organization `json:"publisher,omitempty"`
}

type Author struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	AverageRating *float64 `json:"average_rating,omitempty"`
	BirthDate *string `json:"birth_date,omitempty"`
	FollowersCount *int `json:"followers_count,omitempty"`
	Location *string `json:"location,omitempty"`
	MemberSince *string `json:"member_since,omitempty"`
	Twitter *string `json:"twitter,omitempty"`
	Website *string `json:"website,omitempty"`
	WorksCount *int `json:"works_count,omitempty"`
	Books []Book `json:"books,omitempty"`
}

type Book struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Availability *string `json:"availability,omitempty"`
	AverageRating *float64 `json:"average_rating,omitempty"`
	AwardsWon []string `json:"awards_won,omitempty"`
	Categories []string `json:"categories,omitempty"`
	Characters []string `json:"characters,omitempty"`
	Currency *string `json:"currency,omitempty"`
	CurrentlyReadingCount *int `json:"currently_reading_count,omitempty"`
	DateAdded *string `json:"date_added,omitempty"`
	DateRead *string `json:"date_read,omitempty"`
	DateStarted *string `json:"date_started,omitempty"`
	Format *string `json:"format,omitempty"`
	Genres []string `json:"genres,omitempty"`
	Images *any `json:"images,omitempty"`
	ISBN *string `json:"isbn,omitempty"`
	Isbn13 *string `json:"isbn13,omitempty"`
	Language *string `json:"language,omitempty"`
	OriginalTitle *string `json:"original_title,omitempty"`
	Pages *int `json:"pages,omitempty"`
	Places []string `json:"places,omitempty"`
	Price *string `json:"price,omitempty"`
	PriceAmount *float64 `json:"price_amount,omitempty"`
	Prime *bool `json:"prime,omitempty"`
	Quantity *int `json:"quantity,omitempty"`
	Rating *float64 `json:"rating,omitempty"`
	RatingsCount *int `json:"ratings_count,omitempty"`
	ReviewCount *int `json:"review_count,omitempty"`
	Series *string `json:"series,omitempty"`
	Shelf *string `json:"shelf,omitempty"`
	Sponsored *bool `json:"sponsored,omitempty"`
	ToReadCount *int `json:"to_read_count,omitempty"`
	UserRating *float64 `json:"user_rating,omitempty"`
	WorkURL *string `json:"work_url,omitempty"`
	Brand *Brand `json:"brand,omitempty"`
	Contributors []Author `json:"contributors,omitempty"`
	Manufacturer *Organization `json:"manufacturer,omitempty"`
	Publisher *Organization `json:"publisher,omitempty"`
	WrittenBy *Author `json:"written_by,omitempty"`
}

type Brand struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Country *string `json:"country,omitempty"`
	Founded *string `json:"founded,omitempty"`
	Tagline *string `json:"tagline,omitempty"`
	OwnedBy *Organization `json:"owned_by,omitempty"`
	Website *Website `json:"website,omitempty"`
}

type Channel struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Banner *string `json:"banner,omitempty"`
	SubscriberCount *int `json:"subscriber_count,omitempty"`
	Platform *Product `json:"platform,omitempty"`
}

type Class struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	ActivityType *string `json:"activity_type,omitempty"`
	AllDay *bool `json:"all_day,omitempty"`
	Capacity *int `json:"capacity,omitempty"`
	EndDate *string `json:"end_date,omitempty"`
	EventType *string `json:"event_type,omitempty"`
	IsFull *bool `json:"is_full,omitempty"`
	Recurrence *string `json:"recurrence,omitempty"`
	SpotsRemaining *int `json:"spots_remaining,omitempty"`
	StartDate *string `json:"start_date,omitempty"`
	Timezone *string `json:"timezone,omitempty"`
	Instructor *Person `json:"instructor,omitempty"`
	Involves []Person `json:"involves,omitempty"`
	Location *Place `json:"location,omitempty"`
	Organizer *Person `json:"organizer,omitempty"`
	Venue *Place `json:"venue,omitempty"`
}

type Community struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	AllowCrypto *bool `json:"allow_crypto,omitempty"`
	MemberCount *int `json:"member_count,omitempty"`
	Privacy *string `json:"privacy,omitempty"`
	SubscriberCount *int `json:"subscriber_count,omitempty"`
	Platform *Product `json:"platform,omitempty"`
}

type Conversation struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	AccountEmail *string `json:"account_email,omitempty"`
	IsArchived *bool `json:"is_archived,omitempty"`
	IsGroup *bool `json:"is_group,omitempty"`
	UnreadCount *int `json:"unread_count,omitempty"`
	Message []Message `json:"message,omitempty"`
	Participant []Account `json:"participant,omitempty"`
	Platform *Product `json:"platform,omitempty"`
}

type DnsRecord struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Domain *string `json:"domain,omitempty"`
	RecordName *string `json:"record_name,omitempty"`
	RecordType *string `json:"record_type,omitempty"`
	Ttl *int `json:"ttl,omitempty"`
	Values []string `json:"values,omitempty"`
}

type Domain struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	AutoRenew *bool `json:"auto_renew,omitempty"`
	ExpiresAt *string `json:"expires_at,omitempty"`
	Nameservers []string `json:"nameservers,omitempty"`
	Registrar *string `json:"registrar,omitempty"`
	Status *string `json:"status,omitempty"`
}

type Email struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	AccountEmail *string `json:"account_email,omitempty"`
	Attachments *any `json:"attachments,omitempty"`
	BccRaw *string `json:"bcc_raw,omitempty"`
	BodyHTML *string `json:"body_html,omitempty"`
	CcRaw *string `json:"cc_raw,omitempty"`
	ConversationID *string `json:"conversation_id,omitempty"`
	DeliveredTo *string `json:"delivered_to,omitempty"`
	HasAttachments *bool `json:"has_attachments,omitempty"`
	InReplyTo *string `json:"in_reply_to,omitempty"`
	IsDraft *bool `json:"is_draft,omitempty"`
	IsOutgoing *bool `json:"is_outgoing,omitempty"`
	IsSent *bool `json:"is_sent,omitempty"`
	IsSpam *bool `json:"is_spam,omitempty"`
	IsStarred *bool `json:"is_starred,omitempty"`
	IsTrash *bool `json:"is_trash,omitempty"`
	IsUnread *bool `json:"is_unread,omitempty"`
	LabelIds []string `json:"label_ids,omitempty"`
	MessageID *string `json:"message_id,omitempty"`
	References *string `json:"references,omitempty"`
	ReplyTo *string `json:"reply_to,omitempty"`
	SizeEstimate *int `json:"size_estimate,omitempty"`
	Subject *string `json:"subject,omitempty"`
	ToRaw *string `json:"to_raw,omitempty"`
	Bcc []Account `json:"bcc,omitempty"`
	Cc []Account `json:"cc,omitempty"`
	CcDomain []Domain `json:"cc_domain,omitempty"`
	Domain *Domain `json:"domain,omitempty"`
	From *Account `json:"from,omitempty"`
	InConversation *Conversation `json:"in_conversation,omitempty"`
	Platform *Product `json:"platform,omitempty"`
	RepliesTo *Message `json:"replies_to,omitempty"`
	To []Account `json:"to,omitempty"`
	ToDomain []Domain `json:"to_domain,omitempty"`
}

type Episode struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	DurationMs *int `json:"duration_ms,omitempty"`
	EpisodeNumber *int `json:"episode_number,omitempty"`
	SeasonNumber *int `json:"season_number,omitempty"`
	Guest []Person `json:"guest,omitempty"`
	Series *Podcast `json:"series,omitempty"`
	Transcribe *Transcript `json:"transcribe,omitempty"`
}

type Event struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	AllDay *bool `json:"all_day,omitempty"`
	EndDate *string `json:"end_date,omitempty"`
	EventType *string `json:"event_type,omitempty"`
	Recurrence *string `json:"recurrence,omitempty"`
	StartDate *string `json:"start_date,omitempty"`
	Timezone *string `json:"timezone,omitempty"`
	Involves []Person `json:"involves,omitempty"`
	Location *Place `json:"location,omitempty"`
	Organizer *Person `json:"organizer,omitempty"`
}

type File struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Filename *string `json:"filename,omitempty"`
	Format *string `json:"format,omitempty"`
	MimeType *string `json:"mime_type,omitempty"`
	Path *string `json:"path,omitempty"`
	Size *int `json:"size,omitempty"`
	AttachedTo *Message `json:"attached_to,omitempty"`
}

type Flight struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	ArrivalTime *string `json:"arrival_time,omitempty"`
	CabinClass *string `json:"cabin_class,omitempty"`
	CarbonEmissions *any `json:"carbon_emissions,omitempty"`
	DepartureTime *string `json:"departure_time,omitempty"`
	DurationMinutes *int `json:"duration_minutes,omitempty"`
	FlightNumber *string `json:"flight_number,omitempty"`
	Stops *int `json:"stops,omitempty"`
	Aircraft *Aircraft `json:"aircraft,omitempty"`
	Airline *Airline `json:"airline,omitempty"`
	ArrivesAt *Airport `json:"arrives_at,omitempty"`
	DepartsFrom *Airport `json:"departs_from,omitempty"`
	Layovers []Airport `json:"layovers,omitempty"`
}

type Folder struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	HasReadme *bool `json:"has_readme,omitempty"`
	Path *string `json:"path,omitempty"`
	WorkspaceType *string `json:"workspace_type,omitempty"`
	Contains []File `json:"contains,omitempty"`
	Repository *Repository `json:"repository,omitempty"`
}

type GitCommit struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Additions *int `json:"additions,omitempty"`
	CommittedAt *string `json:"committed_at,omitempty"`
	Deletions *int `json:"deletions,omitempty"`
	FilesChanged *int `json:"files_changed,omitempty"`
	Message *string `json:"message,omitempty"`
	Sha *string `json:"sha,omitempty"`
	Author *Account `json:"author,omitempty"`
	Committer *Account `json:"committer,omitempty"`
	Parent *GitCommit `json:"parent,omitempty"`
	Repository *Repository `json:"repository,omitempty"`
}

type Hardware struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Availability *string `json:"availability,omitempty"`
	Categories []string `json:"categories,omitempty"`
	Currency *string `json:"currency,omitempty"`
	Images *any `json:"images,omitempty"`
	ModelNumber *string `json:"model_number,omitempty"`
	Price *string `json:"price,omitempty"`
	PriceAmount *float64 `json:"price_amount,omitempty"`
	Prime *bool `json:"prime,omitempty"`
	Quantity *int `json:"quantity,omitempty"`
	Rating *float64 `json:"rating,omitempty"`
	RatingsCount *int `json:"ratings_count,omitempty"`
	ReviewCount *int `json:"review_count,omitempty"`
	SerialNumber *string `json:"serial_number,omitempty"`
	Specs *any `json:"specs,omitempty"`
	Sponsored *bool `json:"sponsored,omitempty"`
	Brand *Brand `json:"brand,omitempty"`
	Manufacturer *Organization `json:"manufacturer,omitempty"`
}

type Highlight struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Color *string `json:"color,omitempty"`
	Position *string `json:"position,omitempty"`
	CreatedBy *Person `json:"created_by,omitempty"`
	ExtractedFrom *Book `json:"extracted_from,omitempty"`
}

type Image struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	AltText *string `json:"alt_text,omitempty"`
	Filename *string `json:"filename,omitempty"`
	Format *string `json:"format,omitempty"`
	Height *int `json:"height,omitempty"`
	MimeType *string `json:"mime_type,omitempty"`
	Path *string `json:"path,omitempty"`
	Size *int `json:"size,omitempty"`
	Width *int `json:"width,omitempty"`
	AttachedTo *Message `json:"attached_to,omitempty"`
}

type List struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	IsDefault *bool `json:"is_default,omitempty"`
	IsPublic *bool `json:"is_public,omitempty"`
	ListType *string `json:"list_type,omitempty"`
	Privacy *string `json:"privacy,omitempty"`
	BelongsTo *Account `json:"belongs_to,omitempty"`
	Contains []Product `json:"contains,omitempty"`
	Platform *Product `json:"platform,omitempty"`
}

type Meeting struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	AllDay *bool `json:"all_day,omitempty"`
	CalendarLink *string `json:"calendar_link,omitempty"`
	EndDate *string `json:"end_date,omitempty"`
	EventType *string `json:"event_type,omitempty"`
	IsVirtual *bool `json:"is_virtual,omitempty"`
	MeetingURL *string `json:"meeting_url,omitempty"`
	Recurrence *string `json:"recurrence,omitempty"`
	StartDate *string `json:"start_date,omitempty"`
	Timezone *string `json:"timezone,omitempty"`
	Involves []Person `json:"involves,omitempty"`
	Location *Place `json:"location,omitempty"`
	Organizer *Person `json:"organizer,omitempty"`
	Transcribe *Transcript `json:"transcribe,omitempty"`
}

type Message struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	ConversationID *string `json:"conversation_id,omitempty"`
	IsOutgoing *bool `json:"is_outgoing,omitempty"`
	From *Account `json:"from,omitempty"`
	InConversation *Conversation `json:"in_conversation,omitempty"`
	Platform *Product `json:"platform,omitempty"`
	RepliesTo *Message `json:"replies_to,omitempty"`
}

type Note struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	IsPinned *bool `json:"is_pinned,omitempty"`
	NoteType *string `json:"note_type,omitempty"`
	CreatedBy *Person `json:"created_by,omitempty"`
	ExtractedFrom *Webpage `json:"extracted_from,omitempty"`
	References []Note `json:"references,omitempty"`
}

type Offer struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Availability *string `json:"availability,omitempty"`
	BookingToken *string `json:"booking_token,omitempty"`
	Currency *string `json:"currency,omitempty"`
	OfferType *string `json:"offer_type,omitempty"`
	Price *float64 `json:"price,omitempty"`
	ValidFrom *string `json:"valid_from,omitempty"`
	ValidUntil *string `json:"valid_until,omitempty"`
	For *Product `json:"for,omitempty"`
	OfferedBy *Organization `json:"offered_by,omitempty"`
}

type Order struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Currency *string `json:"currency,omitempty"`
	DeliveryDate *string `json:"delivery_date,omitempty"`
	Status *string `json:"status,omitempty"`
	Summary *string `json:"summary,omitempty"`
	Total *string `json:"total,omitempty"`
	TotalAmount *float64 `json:"total_amount,omitempty"`
	Contains []Product `json:"contains,omitempty"`
	ShippingAddress *Place `json:"shipping_address,omitempty"`
	Tracking *Webpage `json:"tracking,omitempty"`
}

type Organization struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	ActorType *string `json:"actor_type,omitempty"`
	EmployeeCount *int `json:"employee_count,omitempty"`
	Founded *string `json:"founded,omitempty"`
	Industry *string `json:"industry,omitempty"`
	Domain *Domain `json:"domain,omitempty"`
	Headquarters *Place `json:"headquarters,omitempty"`
	Member []Person `json:"member,omitempty"`
	Website *Website `json:"website,omitempty"`
}

type Person struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	About *string `json:"about,omitempty"`
	ActorType *string `json:"actor_type,omitempty"`
	Birthday *string `json:"birthday,omitempty"`
	FirstName *string `json:"first_name,omitempty"`
	Gender *string `json:"gender,omitempty"`
	JoinedDate *string `json:"joined_date,omitempty"`
	LastActive *string `json:"last_active,omitempty"`
	LastName *string `json:"last_name,omitempty"`
	MiddleName *string `json:"middle_name,omitempty"`
	Nickname *string `json:"nickname,omitempty"`
	Notes *string `json:"notes,omitempty"`
	Accounts []Account `json:"accounts,omitempty"`
	CurrentlyReading []Book `json:"currently_reading,omitempty"`
	FavoriteBooks []Book `json:"favorite_books,omitempty"`
	Location *Place `json:"location,omitempty"`
	Roles []Role `json:"roles,omitempty"`
	Website *Website `json:"website,omitempty"`
}

type Place struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Accuracy *string `json:"accuracy,omitempty"`
	City *string `json:"city,omitempty"`
	Country *string `json:"country,omitempty"`
	CountryCode *string `json:"country_code,omitempty"`
	District *string `json:"district,omitempty"`
	FeatureType *string `json:"feature_type,omitempty"`
	FullAddress *string `json:"full_address,omitempty"`
	Latitude *float64 `json:"latitude,omitempty"`
	Locality *string `json:"locality,omitempty"`
	Longitude *float64 `json:"longitude,omitempty"`
	MapboxID *string `json:"mapbox_id,omitempty"`
	Neighborhood *string `json:"neighborhood,omitempty"`
	PlaceFormatted *string `json:"place_formatted,omitempty"`
	PostalCode *string `json:"postal_code,omitempty"`
	Region *string `json:"region,omitempty"`
	Street *string `json:"street,omitempty"`
	StreetNumber *string `json:"street_number,omitempty"`
	WikidataID *string `json:"wikidata_id,omitempty"`
}

type Playlist struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	IsDefault *bool `json:"is_default,omitempty"`
	IsPublic *bool `json:"is_public,omitempty"`
	ListType *string `json:"list_type,omitempty"`
	Privacy *string `json:"privacy,omitempty"`
	BelongsTo *Account `json:"belongs_to,omitempty"`
	Contains []Video `json:"contains,omitempty"`
	Platform *Product `json:"platform,omitempty"`
}

type Podcast struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	FeedURL *string `json:"feed_url,omitempty"`
	Episode []Episode `json:"episode,omitempty"`
	Host []Person `json:"host,omitempty"`
	Platform *Product `json:"platform,omitempty"`
}

type Post struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	CommentCount *int `json:"comment_count,omitempty"`
	ExternalURL *string `json:"external_url,omitempty"`
	Likes *int `json:"likes,omitempty"`
	PostType *string `json:"post_type,omitempty"`
	Score *int `json:"score,omitempty"`
	ViewCount *int `json:"view_count,omitempty"`
	Attachment []File `json:"attachment,omitempty"`
	Contains []Video `json:"contains,omitempty"`
	Media []Image `json:"media,omitempty"`
	PostedBy *Account `json:"posted_by,omitempty"`
	Publish *Community `json:"publish,omitempty"`
	RepliesTo *Post `json:"replies_to,omitempty"`
}

type Product struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Availability *string `json:"availability,omitempty"`
	Categories []string `json:"categories,omitempty"`
	Currency *string `json:"currency,omitempty"`
	Images *any `json:"images,omitempty"`
	Price *string `json:"price,omitempty"`
	PriceAmount *float64 `json:"price_amount,omitempty"`
	Prime *bool `json:"prime,omitempty"`
	Quantity *int `json:"quantity,omitempty"`
	Rating *float64 `json:"rating,omitempty"`
	RatingsCount *int `json:"ratings_count,omitempty"`
	ReviewCount *int `json:"review_count,omitempty"`
	Sponsored *bool `json:"sponsored,omitempty"`
	Brand *Brand `json:"brand,omitempty"`
	Manufacturer *Organization `json:"manufacturer,omitempty"`
}

type Project struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Color *string `json:"color,omitempty"`
	State *string `json:"state,omitempty"`
}

type Quote struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Context *string `json:"context,omitempty"`
	AppearsIn *Book `json:"appears_in,omitempty"`
	SpokenBy *Person `json:"spoken_by,omitempty"`
}

type Repository struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	DefaultBranch *string `json:"default_branch,omitempty"`
	Forks *int `json:"forks,omitempty"`
	IsArchived *bool `json:"is_archived,omitempty"`
	IsPrivate *bool `json:"is_private,omitempty"`
	Language *string `json:"language,omitempty"`
	License *string `json:"license,omitempty"`
	OpenIssues *int `json:"open_issues,omitempty"`
	Size *int `json:"size,omitempty"`
	Stars *int `json:"stars,omitempty"`
	Topics []string `json:"topics,omitempty"`
	ForkedFrom *Repository `json:"forked_from,omitempty"`
	Owner *Account `json:"owner,omitempty"`
}

type Result struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	IndexedAt *string `json:"indexed_at,omitempty"`
	ResultType *string `json:"result_type,omitempty"`
}

type Review struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	CommentCount *int `json:"comment_count,omitempty"`
	ExternalURL *string `json:"external_url,omitempty"`
	IsVerified *bool `json:"is_verified,omitempty"`
	Likes *int `json:"likes,omitempty"`
	PostType *string `json:"post_type,omitempty"`
	Rating *float64 `json:"rating,omitempty"`
	RatingMax *float64 `json:"rating_max,omitempty"`
	Score *int `json:"score,omitempty"`
	Tags []string `json:"tags,omitempty"`
	ViewCount *int `json:"view_count,omitempty"`
	Attachment []File `json:"attachment,omitempty"`
	Contains []Video `json:"contains,omitempty"`
	Media []Image `json:"media,omitempty"`
	PostedBy *Account `json:"posted_by,omitempty"`
	Publish *Community `json:"publish,omitempty"`
	RepliesTo *Post `json:"replies_to,omitempty"`
	Reviews *Product `json:"reviews,omitempty"`
}

type Role struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	EndDate *string `json:"end_date,omitempty"`
	RoleType *string `json:"role_type,omitempty"`
	StartDate *string `json:"start_date,omitempty"`
	Title *string `json:"title,omitempty"`
	Organization *Organization `json:"organization,omitempty"`
	Person *Person `json:"person,omitempty"`
}

type Session struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	EndedAt *string `json:"ended_at,omitempty"`
	MessageCount *int `json:"message_count,omitempty"`
	SessionType *string `json:"session_type,omitempty"`
	StartedAt *string `json:"started_at,omitempty"`
	TokenCount *int `json:"token_count,omitempty"`
	Folder *Folder `json:"folder,omitempty"`
	Participant *Actor `json:"participant,omitempty"`
	Project *Project `json:"project,omitempty"`
}

type Shelf struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	IsDefault *bool `json:"is_default,omitempty"`
	IsExclusive *bool `json:"is_exclusive,omitempty"`
	IsPublic *bool `json:"is_public,omitempty"`
	ListType *string `json:"list_type,omitempty"`
	Privacy *string `json:"privacy,omitempty"`
	BelongsTo *Account `json:"belongs_to,omitempty"`
	Contains []Book `json:"contains,omitempty"`
	Platform *Product `json:"platform,omitempty"`
}

type Skill struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Color *string `json:"color,omitempty"`
	Description *string `json:"description,omitempty"`
	Error *string `json:"error,omitempty"`
	SkillID *string `json:"skill_id,omitempty"`
	Status *string `json:"status,omitempty"`
	PrivacyPolicy *Webpage `json:"privacy_policy,omitempty"`
	TermsOfService *Webpage `json:"terms_of_service,omitempty"`
	Website *Website `json:"website,omitempty"`
}

type Software struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Availability *string `json:"availability,omitempty"`
	Categories []string `json:"categories,omitempty"`
	Currency *string `json:"currency,omitempty"`
	Images *any `json:"images,omitempty"`
	License *string `json:"license,omitempty"`
	OpenSource *bool `json:"open_source,omitempty"`
	Platform []string `json:"platform,omitempty"`
	Price *string `json:"price,omitempty"`
	PriceAmount *float64 `json:"price_amount,omitempty"`
	Prime *bool `json:"prime,omitempty"`
	Quantity *int `json:"quantity,omitempty"`
	Rating *float64 `json:"rating,omitempty"`
	RatingsCount *int `json:"ratings_count,omitempty"`
	RepositoryURL *string `json:"repository_url,omitempty"`
	ReviewCount *int `json:"review_count,omitempty"`
	Sponsored *bool `json:"sponsored,omitempty"`
	Version *string `json:"version,omitempty"`
	Brand *Brand `json:"brand,omitempty"`
	Developer *Organization `json:"developer,omitempty"`
	Manufacturer *Organization `json:"manufacturer,omitempty"`
	Repository *Repository `json:"repository,omitempty"`
}

type Task struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Labels []string `json:"labels,omitempty"`
	Priority *int `json:"priority,omitempty"`
	StartedAt *string `json:"started_at,omitempty"`
	State *string `json:"state,omitempty"`
	TargetDate *string `json:"target_date,omitempty"`
	AssignedTo *Person `json:"assigned_to,omitempty"`
	BlockedBy []Task `json:"blocked_by,omitempty"`
	Blocks []Task `json:"blocks,omitempty"`
	Children []Task `json:"children,omitempty"`
	Parent *Task `json:"parent,omitempty"`
	Project *Project `json:"project,omitempty"`
	Repository *Repository `json:"repository,omitempty"`
}

type Transaction struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Amount *float64 `json:"amount,omitempty"`
	Balance *float64 `json:"balance,omitempty"`
	Category *string `json:"category,omitempty"`
	Currency *string `json:"currency,omitempty"`
	Details *any `json:"details,omitempty"`
	Notes *string `json:"notes,omitempty"`
	Pending *bool `json:"pending,omitempty"`
	PostingDate *string `json:"posting_date,omitempty"`
	Recurring *bool `json:"recurring,omitempty"`
	Type *string `json:"type,omitempty"`
	Account *Account `json:"account,omitempty"`
}

type Transcript struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	ContentRole *string `json:"content_role,omitempty"`
	DurationMs *int `json:"duration_ms,omitempty"`
	Language *string `json:"language,omitempty"`
	SegmentCount *int `json:"segment_count,omitempty"`
	Segments *any `json:"segments,omitempty"`
	SourceType *string `json:"source_type,omitempty"`
}

type Vehicle struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Availability *string `json:"availability,omitempty"`
	BodyType *string `json:"body_type,omitempty"`
	Categories []string `json:"categories,omitempty"`
	Color *string `json:"color,omitempty"`
	Currency *string `json:"currency,omitempty"`
	Drivetrain *string `json:"drivetrain,omitempty"`
	FuelType *string `json:"fuel_type,omitempty"`
	Images *any `json:"images,omitempty"`
	Model *string `json:"model,omitempty"`
	Odometer *int `json:"odometer,omitempty"`
	Price *string `json:"price,omitempty"`
	PriceAmount *float64 `json:"price_amount,omitempty"`
	Prime *bool `json:"prime,omitempty"`
	Quantity *int `json:"quantity,omitempty"`
	Rating *float64 `json:"rating,omitempty"`
	RatingsCount *int `json:"ratings_count,omitempty"`
	ReviewCount *int `json:"review_count,omitempty"`
	Sponsored *bool `json:"sponsored,omitempty"`
	Transmission *string `json:"transmission,omitempty"`
	Trim *string `json:"trim,omitempty"`
	Vin *string `json:"vin,omitempty"`
	Year *int `json:"year,omitempty"`
	Brand *Brand `json:"brand,omitempty"`
	Manufacturer *Organization `json:"manufacturer,omitempty"`
}

type Video struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Codec *string `json:"codec,omitempty"`
	DurationMs *int `json:"duration_ms,omitempty"`
	Filename *string `json:"filename,omitempty"`
	Format *string `json:"format,omitempty"`
	FrameRate *float64 `json:"frame_rate,omitempty"`
	MimeType *string `json:"mime_type,omitempty"`
	Path *string `json:"path,omitempty"`
	Resolution *string `json:"resolution,omitempty"`
	Size *int `json:"size,omitempty"`
	AddTo *Playlist `json:"add_to,omitempty"`
	AttachedTo *Message `json:"attached_to,omitempty"`
	Channel *Channel `json:"channel,omitempty"`
	Transcribe *Transcript `json:"transcribe,omitempty"`
}

type Webpage struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	ContentType *string `json:"content_type,omitempty"`
	LastVisitUnix *int `json:"last_visit_unix,omitempty"`
	VisitCount *int `json:"visit_count,omitempty"`
}

type Website struct {
	ID *string `json:"id,omitempty"`
	Name *string `json:"name,omitempty"`
	Text *string `json:"text,omitempty"`
	URL *string `json:"url,omitempty"`
	Image *string `json:"image,omitempty"`
	Author *string `json:"author,omitempty"`
	DatePublished *string `json:"datePublished,omitempty"`
	Content *string `json:"content,omitempty"`
	Anonymous *bool `json:"anonymous,omitempty"`
	ClaimToken *string `json:"claim_token,omitempty"`
	ClaimURL *string `json:"claim_url,omitempty"`
	ExpiresAt *string `json:"expires_at,omitempty"`
	Status *string `json:"status,omitempty"`
	VersionID *string `json:"version_id,omitempty"`
	Domain *Domain `json:"domain,omitempty"`
	OwnedBy *Organization `json:"owned_by,omitempty"`
}
