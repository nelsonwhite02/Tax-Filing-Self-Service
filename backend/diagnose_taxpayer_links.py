
from sqlalchemy import text
from app.core.database import engine

queries = {
    "CONVERSATIONS": """
        SELECT c.status,
               COUNT(*) AS total,
               COUNT(c.taxpayer_id) AS linked_to_taxpayer,
               COUNT(*) FILTER (
                   WHERE c.taxpayer_id IS NULL
               ) AS missing_taxpayer
        FROM conversations c
        JOIN form_definitions fd ON fd.id = c.form_id
        WHERE fd.code IN ('FORM_A', 'FORM_H1', 'FORM_H3')
        GROUP BY c.status
        ORDER BY c.status
    """,
    "ANSWER_OWNERSHIP": """
        SELECT
            COUNT(*) AS answers,
            COUNT(DISTINCT c.taxpayer_id)
                FILTER (WHERE c.taxpayer_id IS NOT NULL)
                AS linked_taxpayers,
            COUNT(*) FILTER (WHERE c.taxpayer_id IS NULL)
                AS answers_without_taxpayer
        FROM answers a
        JOIN conversations c ON c.id = a.conversation_id
        JOIN questions q ON q.id = a.question_id
        JOIN form_definitions fd ON fd.id = q.form_id
        WHERE c.form_id = fd.id
          AND fd.code IN ('FORM_A', 'FORM_H1', 'FORM_H3')
    """,
    "TAXPAYER_PROFILES": """
        SELECT COUNT(*) AS total_taxpayers,
               COUNT(*) FILTER (WHERE is_active) AS active_taxpayers,
               COUNT(phone_number) AS with_phone,
               COUNT(email) AS with_email
        FROM taxpayers
    """
}

with engine.connect() as conn:
    for label, sql in queries.items():
        print(f"\n--- {label} ---")
        for row in conn.execute(text(sql)).mappings():
            print(dict(row))
