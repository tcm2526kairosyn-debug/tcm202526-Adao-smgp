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

        # MEB — candidate typology (Level 1 admissibility, avoids overlay/norm
        # candidates competing as autonomous methodological envelopes)
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS candidate_type VARCHAR(40)"
        ))
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS candidate_role VARCHAR(40)"
        ))
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS eligible_as_primary_envelope BOOLEAN DEFAULT TRUE"
        ))

        # MEB — Stage 3 Level 2 fit criteria C1-C7 (replace Assurance/Agility/
        # Scalability/Hybridisation, which duplicated the AdPO/AsPO signal)
        for col in ('score_c1_responsiveness', 'score_c2_alignment', 'score_c3_traceability',
                    'score_c4_compliance', 'score_c5_pace_criticality',
                    'score_c6_integration_risk', 'score_c7_distributed_support'):
            conn.execute(text(
                f"ALTER TABLE methodology_evidence_base ADD COLUMN IF NOT EXISTS {col} FLOAT DEFAULT 0.5"
            ))

        # MEB — drop criteria superseded by C1-C7 (caused MAVT circularity with AdPO/AsPO)
        for col in ('score_assurance', 'score_agility', 'score_scalability', 'score_hybridisation'):
            conn.execute(text(
                f"ALTER TABLE methodology_evidence_base DROP COLUMN IF EXISTS {col}"
            ))

        # TEB — Stage 4 Level B implementation capability dimensions CD1-CD8
        # (replace traceability/integration/flow_support, expanded to full backbone)
        for col in ('contribution_cd1', 'contribution_cd2', 'contribution_cd3', 'contribution_cd4',
                    'contribution_cd5', 'contribution_cd6', 'contribution_cd7', 'contribution_cd8'):
            conn.execute(text(
                f"ALTER TABLE tool_evidence_base ADD COLUMN IF NOT EXISTS {col} FLOAT DEFAULT 0.5"
            ))

        # TEB — drop criteria superseded by CD1-CD8 (caused MAVT circularity with context_alignment)
        for col in ('score_traceability', 'score_integration', 'score_flow_support'):
            conn.execute(text(
                f"ALTER TABLE tool_evidence_base DROP COLUMN IF EXISTS {col}"
            ))

        # ProjectDecision — align naming with the alignment note's canonical term
        conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='project_decision' AND column_name='governance_register'
                ) THEN
                    ALTER TABLE project_decision RENAME COLUMN governance_register TO decision_control_register;
                END IF;
            END $$;
        """))

        # ProjectDecision — Level 1 / Level A exclusion causes (audit invariant:
        # every screening exclusion is preserved with its cause)
        conn.execute(text(
            "ALTER TABLE project_decision "
            "ADD COLUMN IF NOT EXISTS meb_exclusions JSON"
        ))
        conn.execute(text(
            "ALTER TABLE project_decision "
            "ADD COLUMN IF NOT EXISTS teb_exclusions JSON"
        ))

        # Composite methodological envelope (alignment note §5.1): overlays,
        # norms and complementary methods may join the envelope as justified
        # components instead of competing as autonomous top-1 candidates.
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS compatible_as_component_of JSON"
        ))
        conn.execute(text(
            "ALTER TABLE project_decision "
            "ADD COLUMN IF NOT EXISTS methodological_envelope JSON"
        ))

        conn.commit()
