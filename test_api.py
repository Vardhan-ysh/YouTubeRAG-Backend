"""
Simple test script to verify the YouTube RAG backend is working correctly.
Run this after setting up the environment and database.
"""
import asyncio
import httpx

BASE_URL = "http://localhost:8000"

async def test_video_processing():
    """Test video processing endpoint"""
    print("\n=== Testing Video Processing ===")
    
    async with httpx.AsyncClient() as client:
        # Test with a sample video
        response = await client.post(
            f"{BASE_URL}/video/process",
            json={
                "urls": [
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Replace with your test video
                ]
            },
            timeout=120.0  # Processing can take time
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if data["results"] and len(data["results"]) > 0:
                video_id = data["results"][0].get("video_id")
                print(f"\n✅ Video processed successfully! Video ID: {video_id}")
                return video_id
            else:
                print("\n❌ No results returned")
                return None
        else:
            print("\n❌ Processing failed")
            return None

async def test_chat_query(video_id: str):
    """Test chat query endpoint"""
    print("\n=== Testing Chat Query ===")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/chat/query",
            json={
                "query": "What is this video about?",
                "video_id": video_id
            },
            timeout=60.0
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                print(f"\n✅ Query successful!")
                print(f"Answer: {data.get('answer')[:200]}...")
                print(f"Sources: {len(data.get('sources', []))} chunks")
            else:
                print(f"\n⚠️ Query completed with status: {data.get('status')}")
        else:
            print("\n❌ Query failed")

async def main():
    """Run all tests"""
    print("🚀 Starting YouTube RAG Backend Tests")
    print(f"Testing against: {BASE_URL}")
    
    try:
        # Test video processing
        video_id = await test_video_processing()
        
        if video_id:
            # Wait a moment for processing to complete
            print("\n⏳ Waiting 5 seconds before testing chat...")
            await asyncio.sleep(5)
            
            # Test chat query
            await test_chat_query(video_id)
        
        print("\n✨ Tests completed!")
        
    except httpx.ConnectError:
        print(f"\n❌ Could not connect to {BASE_URL}")
        print("Make sure the server is running: poetry run poe dev")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
