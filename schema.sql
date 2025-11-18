CREATE TABLE IF NOT EXISTS users (
  user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(50) NOT NULL UNIQUE,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  is_active BOOLEAN DEFAULT TRUE,
  role VARCHAR(20) DEFAULT 'user',
  CONSTRAINT chk_role CHECK (role IN ('user', 'admin'))
);
CREATE TABLE IF NOT EXISTS user_profile (
  user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
  age INT,
  region VARCHAR(100),
  bio TEXT,
  preferred_genres JSONB,
  preferred_studios JSONB,
  preferred_themes JSONB,
  filter_settings JSONB,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS anime_catalog (
  anime_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(255) NOT NULL,
  synopsis TEXT,
  release_year INT,
  episodes INT,
  popularity_score FLOAT,
  average_rating FLOAT,
  genres JSONB,
  studios JSONB,
  themes JSONB,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ratings (
  rating_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  anime_id UUID NOT NULL REFERENCES anime_catalog(anime_id) ON DELETE CASCADE,
  score INT NOT NULL CHECK (score >= 0 AND score <= 10),
  review_text TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  UNIQUE (user_id, anime_id)
);

CREATE TABLE IF NOT EXISTS watchlists (
  watchlist_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  name VARCHAR(100) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS watchlist_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  watchlist_id UUID NOT NULL REFERENCES watchlists(watchlist_id) ON DELETE CASCADE,
  anime_id UUID NOT NULL REFERENCES anime_catalog(anime_id) ON DELETE CASCADE,
  priority_rank INT,
  added_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  completed BOOLEAN DEFAULT FALSE,
  rewatch_count INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS notes (
  note_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  anime_id UUID NOT NULL REFERENCES anime_catalog(anime_id) ON DELETE CASCADE,
  note TEXT,
  private BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recommendation_cache (
  user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
  recommended_anime_ids JSONB,
  confidence_score FLOAT,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rating_events_log (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  anime_id UUID,
  score INT,
  event_time TIMESTAMP WITH TIME ZONE DEFAULT now(),
  payload JSONB
);

CREATE TABLE IF NOT EXISTS search_events_log (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  search_query TEXT,
  filters JSONB,
  event_time TIMESTAMP WITH TIME ZONE DEFAULT now(),
  payload JSONB
);

CREATE TABLE IF NOT EXISTS import_jobs (
  job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  admin_user_id UUID,
  status VARCHAR(20) DEFAULT 'pending',
  started_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  completed_at TIMESTAMP WITH TIME ZONE,
  payload JSONB
);
