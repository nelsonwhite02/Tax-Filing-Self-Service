from sqlalchemy import text
from app.core.database import engine

queries = {
    "Conversation form links": """
        SELECT fd.code, c.status,
               COUNT(*) AS conversations,
               COUNT(*) FILTER (WHERE c.form_id IS NULL) AS missing_form_id
        FROM conversations c
        LEFT JOIN form_definitions fd ON fd.id = c.form_id
        GROUP BY fd.code, c.status
        ORDER BY fd.code, c.status
    """,
    "Answers excluded by form link": """
        SELECT fd.code,
               COUNT(*) AS joined_answers,
               COUNT(*) FILTER (
                   WHERE c.form_id = q.form_id
               ) AS answers_passing_form_link,
               COUNT(*) FILTER (
                   WHERE c.form_id IS DISTINCT FROM q.form_id
               ) AS answers_failing_form_link
        FROM answers a
        JOIN questions q ON q.id = a.question_id
        JOIN form_definitions fd ON fd.id = q.form_id
        JOIN conversations c ON c.id = a.conversation_id
        WHERE fd.code IN ('FORM_A', 'FORM_H1', 'FORM_H3')
        GROUP BY fd.code
        ORDER BY fd.code
    """,
}

with engine.connect() as conn:
    for title, sql in queries.items():
        print("\n---", title, "---")
        for row in conn.execute(text(sql)).mappings():
            print(dict(row))
