CREATE TABLE IF NOT EXISTS users (
    userId UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    passwordHash VARCHAR(255) NOT NULL,
    createdTime TIMESTAMP WITH TIME ZONE DEFAULT now(),
    isActive BOOLEAN DEFAULT TRUE,
    role VARCHAR(20) DEFAULT 'user',
    CONSTRAINT chk_role CHECK (role IN ('user', 'admin'))
);

CREATE TABLE IF NOT EXISTS profilePreferences (
    userId UUID PRIMARY KEY,
    demographic JSONB, -- age, region, bio
    preferredGenres JSONB,
    preferredStudios JSONB,
    preferredThemes JSONB,
    filterSettings JSONB,
    tasteSurvey JSONB,
    updateTime TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS animeCatalog (
    animeId VARCHAR(32) PRIMARY KEY,
    coreRecord JSONB NOT NULL, -- title, alternativeTitle, type, year, episodes, malUrl, sequel, imageUrl
    aboutMe JSONB, -- genres, genresDetailed
    popularity JSONB, -- averageRating
    status VARCHAR(20) DEFAULT 'active',
    dataFingerprint VARCHAR(64) UNIQUE,
    updateTime TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ratingSnapshots (
    ratingId UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    userId UUID NOT NULL,
    animeId UUID NOT NULL,
    score SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 10),
    ratingMeta JSONB,
    reviewText TEXT,
    createTime TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE (userId, animeId)
);

CREATE TABLE IF NOT EXISTS ratingHistory (
    historyId UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ratingId UUID NOT NULL,
    priorPayload JSONB NOT NULL,
    changedAt TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS watchlistDocuments (
    watchlistId UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    userId UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    items JSONB NOT NULL,
    metadata JSONB,
    createTime TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updateTime TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS userNotes (
    noteId UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    userId UUID NOT NULL,
    animeId UUID NOT NULL,
    noteText TEXT,
    tags JSONB,
    noteHash CHAR(64) UNIQUE,
    private BOOLEAN DEFAULT TRUE,
    createTime TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recommendationCache (
    cacheId UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    userId UUID NOT NULL UNIQUE,
    payload JSONB NOT NULL,
    sourceMetadata JSONB,
    confidenceScore FLOAT,
    updatedAt TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recommendationAudit (
    auditId UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    userId UUID NOT NULL,
    recommendationSnapshot JSONB NOT NULL,
    generatedBy VARCHAR(50),
    generatedAt TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ratingEventsLog (
    eventId UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    userId UUID,
    animeId UUID,
    score SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 10),
    eventTime TIMESTAMP WITH TIME ZONE DEFAULT now(),
    payload JSONB
);

CREATE TABLE IF NOT EXISTS searchEventsLog (
    eventId UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    userId UUID,
    searchQuery TEXT,
    filters JSONB,
    eventTime TIMESTAMP WITH TIME ZONE DEFAULT now(),
    payload JSONB
);

CREATE TABLE IF NOT EXISTS importJobs (
    jobId UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    adminUserId UUID,
    status VARCHAR(20) DEFAULT 'pending',
    payload JSONB NOT NULL,
    startedAt TIMESTAMP WITH TIME ZONE DEFAULT now(),
    completedAt TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS animeImportMap (
    importId UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    animeId VARCHAR(32) NOT NULL,
    importJobId VARCHAR(32),
    importTime TIMESTAMP WITH TIME ZONE DEFAULT now(),
    importSource VARCHAR(255),
    UNIQUE(animeId, importJobId)
);