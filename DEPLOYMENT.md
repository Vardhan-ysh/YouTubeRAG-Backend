<!-- To create secrets -->
echo -n "your-gemini-api-key" | gcloud secrets create GEMINI_API_KEY --data-file=-
echo -n "your-supabase-url" | gcloud secrets create SUPABASE_URL --data-file=-
echo -n "your-supabase-anon-key" | gcloud secrets create SUPABASE_ANON_KEY --data-file=-
echo -n "your-database-url" | gcloud secrets create DATABASE_URL --data-file=- 
echo -n "your-rapidapi-key" | gcloud secrets create RAPIDAPI_KEY --data-file=-
echo -n "youtube-transcriptor.p.rapidapi.com" | gcloud secrets create RAPIDAPI_HOST --data-file=-
echo -n "en" | gcloud secrets create TRANSCRIPT_LANG --data-file=-

<!-- To update secrets -->
echo -n "your-updated-gemini-api-key" | gcloud secrets versions add GEMINI_API_KEY --data-file=-
echo -n "your-updated-supabase-url" | gcloud secrets versions add SUPABASE_URL --data-file=-
echo -n "your-updated-supabase-anon-key" | gcloud secrets versions add SUPABASE_ANON_KEY --data-file=-
echo -n "your-updated-database-url" | gcloud secrets versions add DATABASE_URL --data-file=-
echo -n "your-updated-rapidapi-key" | gcloud secrets versions add RAPIDAPI_KEY --data-file=-
echo -n "your-updated-rapidapi-host" | gcloud secrets versions add RAPIDAPI_HOST --data-file=-
echo -n "your-updated-transcript-lang" | gcloud secrets versions add TRANSCRIPT_LANG --data-file=-

<!-- To delete secrets -->
gcloud secrets delete GEMINI_API_KEY --quiet
gcloud secrets delete SUPABASE_URL --quiet
gcloud secrets delete SUPABASE_ANON_KEY --quiet
gcloud secrets delete DATABASE_URL --quiet
gcloud secrets delete RAPIDAPI_KEY --quiet
gcloud secrets delete RAPIDAPI_HOST --quiet
gcloud secrets delete TRANSCRIPT_LANG --quiet

<!-- To build docker image -->
docker build -t gcr.io/$(gcloud config get-value project)/youtube-rag-backend:latest .

<!-- To upload the Docker image -->
docker push gcr.io/youtuberag-477113/youtube-rag-backend:latest

<!-- To run -->
gcloud run deploy youtube-rag-backend `
  --image gcr.io/youtuberag-477113/youtube-rag-backend:latest `
  --platform managed `
  --region us-central1 `
  --allow-unauthenticated `
  --memory 256Mi `
  --cpu 0.25 `
  --timeout 60 `
  --max-instances 1 `
  --min-instances 0 `
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,SUPABASE_URL=SUPABASE_URL:latest,SUPABASE_ANON_KEY=SUPABASE_ANON_KEY:latest,DATABASE_URL=DATABASE_URL:latest,RAPIDAPI_KEY=RAPIDAPI_KEY:latest,RAPIDAPI_HOST=RAPIDAPI_HOST:latest,TRANSCRIPT_LANG=TRANSCRIPT_LANG:latest"