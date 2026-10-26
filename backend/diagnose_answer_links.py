from sqlalchemy import text
from app.core.database import engine

sql = """
SELECT
    COUNT(*) AS total_answers,
    COUNT(q.id) AS answers_with_question,
    COUNT(*) FILTER (WHERE q.form_id IS NULL) AS questions_without_form,
    COUNT(*) FILTER (WHERE c.form_id IS NULL) AS conversations_without_form,
    COUNT(*) FILTER (
        WHERE q.form_id = c.form_id
    ) AS matching_form_links,
    COUNT(*) FILTER (
        WHERE q.form_id IS DISTINCT FROM c.form_id
    ) AS mismatched_form_links
FROM answers a
LEFT JOIN questions q ON q.id = a.question_id
LEFT JOIN conversations c ON c.id = a.conversation_id
"""

with engine.connect() as conn:
    print(dict(conn.execute(text(sql)).mappings().one()))

    print("\n--- Answer counts by conversation form ---")
    rows = conn.execute(text("""
        SELECT fd.code, COUNT(a.id) AS answer_count
        FROM answers a
        JOIN conversations c ON c.id = a.conversation_id
        LEFT JOIN form_definitions fd ON fd.id = c.form_id
        GROUP BY fd.code
        ORDER BY fd.code
    """)).mappings()

    for row in rows:
        print(dict(row))
