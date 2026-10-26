
from sqlalchemy import text
from app.core.database import engine

queries = {
    "FORM_COUNTS": """
        SELECT fd.code AS form_code,
               COUNT(*) AS answer_count,
               COUNT(DISTINCT q.id) AS question_count,
               COUNT(DISTINCT c.id) AS conversation_count
        FROM answers a
        JOIN questions q ON q.id = a.question_id
        JOIN conversations c ON c.id = a.conversation_id
        JOIN form_definitions fd ON fd.id = q.form_id
        WHERE c.form_id = fd.id
          AND fd.code IN ('FORM_A', 'FORM_H1', 'FORM_H3')
        GROUP BY fd.code
        ORDER BY fd.code
    """,
    "QUESTION_COUNTS": """
        SELECT q.code, COUNT(*) AS answer_count
        FROM answers a
        JOIN questions q ON q.id = a.question_id
        JOIN conversations c ON c.id = a.conversation_id
        JOIN form_definitions fd ON fd.id = q.form_id
        WHERE c.form_id = fd.id
          AND fd.code IN ('FORM_A', 'FORM_H1', 'FORM_H3')
        GROUP BY q.code
        ORDER BY q.code
    """
}

with engine.connect() as conn:
    for label, sql in queries.items():
        print(f"\n--- {label} ---")
        for row in conn.execute(text(sql)).mappings():
            print(dict(row))
