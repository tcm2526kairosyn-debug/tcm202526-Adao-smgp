from sqlalchemy import text


def run_migrations(db):
    """Apply incremental schema changes without Alembic."""
    with db.engine.connect() as conn:
        # MEB — soft-delete
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"
        ))
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS inactive_date TIMESTAMP"
        ))

        # TEB — soft-delete
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"
        ))
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS inactive_date TIMESTAMP"
        ))

        # MEB — SCD Type-2 audit columns
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS active_date TIMESTAMP"
        ))
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS updated_by VARCHAR(80)"
        ))
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "DROP CONSTRAINT IF EXISTS methodology_evidence_base_code_key"
        ))

        # TEB — SCD Type-2 audit columns
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS active_date TIMESTAMP"
        ))
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS updated_by VARCHAR(80)"
        ))
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "DROP CONSTRAINT IF EXISTS tool_evidence_base_code_key"
        ))

        # MCDMWeights — SCD Type-2 audit columns
        conn.execute(text(
            "ALTER TABLE mcdm_weights "
            "ADD COLUMN IF NOT EXISTS active_date TIMESTAMP"
        ))
        conn.execute(text(
            "ALTER TABLE mcdm_weights "
            "ADD COLUMN IF NOT EXISTS inactive_date TIMESTAMP"
        ))
        conn.execute(text(
            "ALTER TABLE mcdm_weights "
            "ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"
        ))
        # Remove unique constraint so multiple versions can share the same context
        conn.execute(text(
            "ALTER TABLE mcdm_weights "
            "DROP CONSTRAINT IF EXISTS mcdm_weights_context_key"
        ))

        # Back-fill nulls from existing rows
        conn.execute(text(
            "UPDATE methodology_evidence_base SET is_active = TRUE WHERE is_active IS NULL"
        ))
        conn.execute(text(
            "UPDATE methodology_evidence_base SET active_date = NOW() WHERE active_date IS NULL"
        ))
        conn.execute(text(
            "UPDATE tool_evidence_base SET is_active = TRUE WHERE is_active IS NULL"
        ))
        conn.execute(text(
            "UPDATE tool_evidence_base SET active_date = NOW() WHERE active_date IS NULL"
        ))
        conn.execute(text(
            "UPDATE mcdm_weights SET is_active = TRUE WHERE is_active IS NULL"
        ))
        conn.execute(text(
            "UPDATE mcdm_weights SET active_date = updated_at WHERE active_date IS NULL"
        ))

        # Projetos — widen equipa_projeto to TEXT for JSON storage
        conn.execute(text(
            "ALTER TABLE projetos ALTER COLUMN equipa_projeto TYPE TEXT"
        ))

        # MEB — spec-aligned posture coordinates {1,2,3,4}
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS ag_posture INTEGER DEFAULT 2"
        ))
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS as_posture INTEGER DEFAULT 2"
        ))

        # MEB — spec-aligned MCDM criteria (replaces old flexibility/speed/risk/stakeholder)
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS score_assurance FLOAT DEFAULT 0.5"
        ))
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS score_agility FLOAT DEFAULT 0.5"
        ))
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS score_scalability FLOAT DEFAULT 0.5"
        ))
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS score_hybridisation FLOAT DEFAULT 0.5"
        ))

        # TEB — spec-aligned context coordinates {1,2,3,4}
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS agility_support INTEGER DEFAULT 2"
        ))
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS assurance_support INTEGER DEFAULT 2"
        ))

        # TEB — spec-aligned MCDM criteria (replaces old ease_of_use/reporting/scalability)
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS score_traceability FLOAT DEFAULT 0.5"
        ))
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS score_flow_support FLOAT DEFAULT 0.5"
        ))

        # MEB — drop legacy columns no longer used by the motor
        for col in ('min_agpi', 'max_aspi', 'score_flexibility',
                    'score_traceability', 'score_speed', 'score_risk_control',
                    'score_stakeholder_eng'):
            conn.execute(text(
                f"ALTER TABLE methodology_evidence_base DROP COLUMN IF EXISTS {col}"
            ))

        # TEB — drop legacy columns never used by the motor
        for col in ('requires_cloud', 'score_ease_of_use', 'score_reporting', 'score_scalability'):
            conn.execute(text(
                f"ALTER TABLE tool_evidence_base DROP COLUMN IF EXISTS {col}"
            ))

        # TEB — convert category from VARCHAR to JSON array (multi-category support)
        conn.execute(text("""
            ALTER TABLE tool_evidence_base
            ALTER COLUMN category TYPE JSON
            USING CASE
                WHEN category IS NULL THEN '[]'::json
                WHEN category::text LIKE '[%' THEN category::json
                ELSE json_build_array(category)
            END
        """))

        conn.commit()
