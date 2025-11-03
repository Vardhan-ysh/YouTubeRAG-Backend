"""
Utility functions for managing video embeddings.
Can be run as a standalone script for maintenance tasks.
"""
from app.utils.supabase_client import cleanup_expired_embeddings, supabase
from datetime import datetime

def cleanup():
    """Remove expired embeddings from database"""
    print("🧹 Starting cleanup of expired embeddings...")
    cleanup_expired_embeddings()
    print("✅ Cleanup completed!")

def list_videos():
    """List all videos in the database"""
    print("\n📋 Listing all videos in database:\n")
    
    try:
        result = supabase.table("video_status").select("*").execute()
        
        if result.data:
            print(f"Found {len(result.data)} video(s):\n")
            for video in result.data:
                print(f"Video ID: {video['video_id']}")
                print(f"Status: {video['status']}")
                print(f"Updated: {video['updated_at']}")
                print("-" * 50)
        else:
            print("No videos found in database.")
    except Exception as e:
        print(f"❌ Error: {e}")

def get_video_stats(video_id: str):
    """Get statistics for a specific video"""
    print(f"\n📊 Statistics for video: {video_id}\n")
    
    try:
        # Get video status
        status_result = supabase.table("video_status").select("*").eq("video_id", video_id).execute()
        
        if not status_result.data:
            print("❌ Video not found in database.")
            return
        
        status = status_result.data[0]
        print(f"Status: {status['status']}")
        print(f"Created: {status['created_at']}")
        print(f"Updated: {status['updated_at']}")
        
        # Get embeddings count
        embeddings_result = supabase.table("video_embeddings")\
            .select("chunk_index, expiry_date", count="exact")\
            .eq("video_id", video_id)\
            .execute()
        
        if embeddings_result.data:
            print(f"\nTotal Chunks: {len(embeddings_result.data)}")
            
            # Check expiry
            first_chunk = embeddings_result.data[0]
            expiry = datetime.fromisoformat(first_chunk['expiry_date'].replace('Z', '+00:00'))
            now = datetime.now(expiry.tzinfo)
            
            if expiry > now:
                time_left = expiry - now
                print(f"Expires in: {time_left.days} days, {time_left.seconds // 3600} hours")
            else:
                print("⚠️ Embeddings have expired!")
        else:
            print("\nNo embeddings found for this video.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def delete_video(video_id: str):
    """Delete a video and all its embeddings"""
    print(f"\n🗑️ Deleting video: {video_id}")
    
    confirm = input("Are you sure? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Deletion cancelled.")
        return
    
    try:
        # Delete embeddings
        supabase.table("video_embeddings").delete().eq("video_id", video_id).execute()
        # Delete status
        supabase.table("video_status").delete().eq("video_id", video_id).execute()
        
        print("✅ Video deleted successfully!")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Main menu for utility functions"""
    print("🛠️ YouTube RAG Utilities")
    print("\nAvailable commands:")
    print("1. Cleanup expired embeddings")
    print("2. List all videos")
    print("3. Get video statistics")
    print("4. Delete video")
    print("5. Exit")
    
    while True:
        choice = input("\nEnter command number: ").strip()
        
        if choice == "1":
            cleanup()
        elif choice == "2":
            list_videos()
        elif choice == "3":
            video_id = input("Enter video ID: ").strip()
            get_video_stats(video_id)
        elif choice == "4":
            video_id = input("Enter video ID: ").strip()
            delete_video(video_id)
        elif choice == "5":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1-5.")

if __name__ == "__main__":
    main()
