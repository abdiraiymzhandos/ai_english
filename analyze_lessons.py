import psycopg2
from psycopg2.extras import RealDictCursor

def analyze_lessons():
    # Connect to PostgreSQL database
    conn = psycopg2.connect(
        dbname="blog_database",
        user="zhandos",
        password="Aaa12345",
        host="localhost",
        port="5432"
    )
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get all lessons with IDs
    cursor.execute('''
        SELECT id, title, content, grammar, dialogue, vocabulary
        FROM lessons_lesson
    ''')
    
    lessons = cursor.fetchall()
    
    # Keywords that indicate valuable content (in both English and Kazakh)
    valuable_keywords = [
        # Basic and essential topics
        'essential', 'important', 'basic', 'fundamental', 'common',
        'басты', 'маңызды', 'негізгі', 'қажетті', 'күнделікті',
        
        # Business and work
        'business', 'interview', 'job', 'work', 'career',
        'бизнес', 'жұмыс', 'мансап', 'сұхбат',
        
        # Daily life and travel
        'travel', 'daily', 'routine', 'everyday', 'life',
        'саяхат', 'күнделікті', 'өмір', 'тұрмыс',
        
        # Language skills
        'conversation', 'speaking', 'grammar', 'pronunciation',
        'сөйлесу', 'грамматика', 'айту', 'pronunciation'
    ]
    
    # Score each lesson
    scored_lessons = []
    for lesson in lessons:
        title = lesson['title']
        content = lesson['content'] or ''
        grammar = lesson['grammar'] or ''
        dialogue = lesson['dialogue'] or ''
        vocabulary = lesson['vocabulary'] or ''
        lesson_id = lesson['id']
        
        score = 0
        
        # Base score for having complete content
        if content and grammar and dialogue and vocabulary:
            score += 10
        
        # Score based on content completeness
        score += len(content.split()) * 0.01  # More content is valuable
        score += len(grammar.split()) * 0.02  # Grammar is important
        score += len(dialogue.split()) * 0.02  # Practical dialogues are valuable
        score += len(vocabulary.split()) * 0.015  # Vocabulary is useful
        
        # Score based on valuable keywords
        all_text = f"{title} {content} {grammar} {dialogue} {vocabulary}".lower()
        
        for keyword in valuable_keywords:
            if keyword in title.lower():
                score += 5  # Keywords in title are very important
            if keyword in all_text:
                score += 2  # Keywords in content are valuable
        
        scored_lessons.append({
            'id': lesson_id,
            'title': title,
            'score': score,
            'content_preview': content[:100] + '...' if len(content) > 100 else content
        })
    
    # Sort by score and get top 3
    scored_lessons.sort(key=lambda x: x['score'], reverse=True)
    top_3 = scored_lessons[:3]
    
    print("\nTop 3 most valuable lessons for free promotion:")
    print("=" * 80)
    for lesson in top_3:
        print(f"ID: {lesson['id']}")
        print(f"Title: {lesson['title']}")
        print(f"Value Score: {lesson['score']:.2f}")
        print(f"Content Preview: {lesson['content_preview']}")
        print("-" * 80)
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    analyze_lessons() 