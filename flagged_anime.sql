
CREATE TABLE "flagged_anime" (
    "flagId" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "animeId" UUID NOT NULL,
    "userId" UUID NOT NULL,
    "reason" TEXT NOT NULL,
    "status" VARCHAR(20) DEFAULT 'pending' CHECK ("status" IN ('pending', 'resolved', 'dismissed')),
    "createdTime" TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY ("animeId") REFERENCES "animeCatalog"("animeId"),
    FOREIGN KEY ("userId") REFERENCES "users"("userId")
);
