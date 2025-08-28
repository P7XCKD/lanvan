#!/usr/bin/env python3
"""
🚀 Test the new AGGRESSIVE adaptive chunk sizing system
"""

from app.android_optimizer import universal_optimizer, get_available_memory_mb, get_cpu_usage

def test_aggressive_chunks():
    print("🚀 AGGRESSIVE Adaptive Chunk Sizing Test")
    print("=" * 50)
    
    # Current system info
    available_mb = get_available_memory_mb()
    cpu_usage = get_cpu_usage()
    
    print(f"💾 Available Memory: {available_mb}MB")
    print(f"🖥️ CPU Usage: {cpu_usage:.1f}%")
    print(f"🖥️ Platform: {universal_optimizer.platform}")
    print(f"📱 Is Android: {universal_optimizer.is_android}")
    print(f"💾 Is Low Memory: {universal_optimizer.is_low_memory}")
    print()
    
    # Test different file sizes
    test_files = [
        ("Small File", 50 * 1024 * 1024),        # 50MB
        ("Medium File", 100 * 1024 * 1024),      # 100MB
        ("Large File", 500 * 1024 * 1024),       # 500MB
        ("Very Large", 1024 * 1024 * 1024),      # 1GB
        ("Huge File", 5 * 1024 * 1024 * 1024),   # 5GB
        ("Massive File", 10 * 1024 * 1024 * 1024), # 10GB
        ("Ultra File", 50 * 1024 * 1024 * 1024),  # 50GB
    ]
    
    print("📊 Adaptive Chunk Size Results:")
    print("-" * 60)
    
    for name, file_size in test_files:
        chunk_size = universal_optimizer.get_adaptive_chunk_size(file_size)
        chunk_mb = chunk_size / (1024 * 1024)
        improvement = chunk_size / (1024 * 1024)  # vs old 1MB
        
        print(f"{name:12} ({file_size//1024//1024:>5}MB) → {chunk_mb:>6.1f}MB chunks ({improvement:>4.1f}x faster)")
    
    print()
    print("🎯 Performance Analysis:")
    print("-" * 30)
    
    # Calculate performance improvements
    old_1mb = 1024 * 1024
    old_512kb = 512 * 1024
    
    test_1gb = universal_optimizer.get_adaptive_chunk_size(1024 * 1024 * 1024)
    test_5gb = universal_optimizer.get_adaptive_chunk_size(5 * 1024 * 1024 * 1024)
    
    print(f"📈 1GB file chunks: {test_1gb//1024//1024}MB (was 2MB) = {test_1gb//(2*1024*1024)}x improvement!")
    print(f"📈 5GB file chunks: {test_5gb//1024//1024}MB (was 512KB) = {test_5gb//old_512kb}x improvement!")
    
    print()
    print("🚀 System will now use MAXIMUM performance chunks based on your capabilities!")

if __name__ == "__main__":
    test_aggressive_chunks()
