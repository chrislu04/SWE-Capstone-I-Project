DROP TABLE IF EXISTS "ratingEventsLog" CASCADE;
DROP TABLE IF EXISTS "searchEventsLog" CASCADE;
DROP TABLE IF EXISTS "ratingHistory" CASCADE;
DROP TABLE IF EXISTS "ratingSnapshots" CASCADE;
DROP TABLE IF EXISTS "userNotes" CASCADE;
DROP TABLE IF EXISTS "recommendationAudit" CASCADE;
DROP TABLE IF EXISTS "recommendationCache" CASCADE;
DROP TABLE IF EXISTS "animeGenresDetailed" CASCADE;
DROP TABLE IF EXISTS "animeGenres" CASCADE;
DROP TABLE IF EXISTS "animeCatalog" CASCADE;
DROP TABLE IF EXISTS "watchlistDocuments" CASCADE;
DROP TABLE IF EXISTS "profilePreferences" CASCADE;
DROP TABLE IF EXISTS "importJobs" CASCADE;
DROP TABLE IF EXISTS "users" CASCADE;

CREATE TABLE "users" (
    "userId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "username" VARCHAR(50) UNIQUE NOT NULL,
    "email" VARCHAR(255) UNIQUE NOT NULL,
    "passwordHash" VARCHAR(255) NOT NULL,
    "createdTime" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    "isActive" BOOLEAN DEFAULT TRUE,
    "role" VARCHAR(20) DEFAULT 'user' CHECK ("role" IN ('user', 'admin'))
);

CREATE TABLE "profilePreferences" (
    "userId" UUID PRIMARY KEY REFERENCES "users"("userId") ON DELETE CASCADE,
    "demographic" JSONB,
    "preferredGenres" JSONB,
    "preferredStudios" JSONB,
    "preferredThemes" JSONB,
    "filterSettings" JSONB,
    "tasteSurvey" JSONB,
    "updateTime" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE "animeCatalog" (
    "animeId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "title" VARCHAR(255) NOT NULL,
    "alternativeTitle" VARCHAR(255),
    "type" VARCHAR(50),
    "releaseYear" INTEGER,
    "episodes" INTEGER,
    "malUrl" TEXT,
    "sequel" BOOLEAN DEFAULT FALSE,
    "imageUrl" TEXT,
    "averageRating" FLOAT,
    "status" VARCHAR(20) DEFAULT 'active',
    "updateTime" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE("title", "releaseYear")
);

CREATE TABLE "animeGenres" (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "animeId" UUID NOT NULL REFERENCES "animeCatalog"("animeId") ON DELETE CASCADE,
    "genre" VARCHAR(100) NOT NULL,
    UNIQUE("animeId", "genre")
);

CREATE TABLE "animeGenresDetailed" (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "animeId" UUID NOT NULL REFERENCES "animeCatalog"("animeId") ON DELETE CASCADE,
    "genreDetail" VARCHAR(100) NOT NULL,
    UNIQUE("animeId", "genreDetail")
);

CREATE TABLE "ratingSnapshots" (
    "ratingId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "userId" UUID NOT NULL REFERENCES "users"("userId") ON DELETE CASCADE,
    "animeId" UUID NOT NULL REFERENCES "animeCatalog"("animeId") ON DELETE CASCADE,
    "score" SMALLINT NOT NULL CHECK ("score" >= 0 AND "score" <= 10),
    "ratingMeta" JSONB,
    "reviewText" TEXT,
    "createTime" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE("userId", "animeId")
);

CREATE TABLE "ratingHistory" (
    "historyId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "ratingId" UUID NOT NULL REFERENCES "ratingSnapshots"("ratingId") ON DELETE CASCADE,
    "priorPayload" JSONB NOT NULL,
    "changedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE "watchlistDocuments" (
    "watchlistId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "userId" UUID NOT NULL REFERENCES "users"("userId") ON DELETE CASCADE,
    "name" VARCHAR(100) NOT NULL,
    "items" JSONB NOT NULL,
    "watchlistMetadata" JSONB,
    "createTime" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    "updateTime" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE "userNotes" (
    "noteId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "userId" UUID NOT NULL REFERENCES "users"("userId") ON DELETE CASCADE,
    "animeId" UUID NOT NULL REFERENCES "animeCatalog"("animeId") ON DELETE CASCADE,
    "noteText" TEXT,
    "tags" JSONB,
    "noteHash" VARCHAR(64) UNIQUE,
    "private" BOOLEAN DEFAULT TRUE,
    "createTime" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE "recommendationCache" (
    "cacheId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "userId" UUID UNIQUE NOT NULL REFERENCES "users"("userId") ON DELETE CASCADE,
    "payload" JSONB NOT NULL,
    "sourceMetadata" JSONB,
    "confidenceScore" FLOAT,
    "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE "recommendationAudit" (
    "auditId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "userId" UUID NOT NULL REFERENCES "users"("userId") ON DELETE CASCADE,
    "recommendationSnapshot" JSONB NOT NULL,
    "generatedBy" VARCHAR(50),
    "generatedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE "ratingEventsLog" (
    "eventId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "userId" UUID REFERENCES "users"("userId") ON DELETE SET NULL,
    "animeId" UUID REFERENCES "animeCatalog"("animeId") ON DELETE SET NULL,
    "score" SMALLINT NOT NULL CHECK ("score" >= 0 AND "score" <= 10),
    "eventTime" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    "payload" JSONB
);

CREATE TABLE "searchEventsLog" (
    "eventId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "userId" UUID REFERENCES "users"("userId") ON DELETE SET NULL,
    "searchQuery" TEXT,
    "filters" JSONB,
    "eventTime" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    "payload" JSONB
);

CREATE TABLE "importJobs" (
    "jobId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "adminUserId" UUID REFERENCES "users"("userId") ON DELETE SET NULL,
    "status" VARCHAR(20) DEFAULT 'pending',
    "payload" JSONB NOT NULL,
    "startedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    "completedAt" TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_anime_title ON "animeCatalog"("title");
CREATE INDEX idx_anime_year ON "animeCatalog"("releaseYear");
CREATE INDEX idx_anime_rating ON "animeCatalog"("averageRating");
CREATE INDEX idx_genre ON "animeGenres"("genre");
CREATE INDEX idx_genre_detail ON "animeGenresDetailed"("genreDetail");
CREATE INDEX idx_rating_user ON "ratingSnapshots"("userId");
CREATE INDEX idx_rating_anime ON "ratingSnapshots"("animeId");
CREATE INDEX idx_watchlist_user ON "watchlistDocuments"("userId");
CREATE INDEX idx_user_note_user ON "userNotes"("userId");
CREATE INDEX idx_user_note_anime ON "userNotes"("animeId");
CREATE INDEX idx_rec_cache_user ON "recommendationCache"("userId");
CREATE INDEX idx_rec_audit_user ON "recommendationAudit"("userId");
CREATE INDEX idx_rating_event_user ON "ratingEventsLog"("userId");
CREATE INDEX idx_rating_event_anime ON "ratingEventsLog"("animeId");
CREATE INDEX idx_search_event_user ON "searchEventsLog"("userId");
