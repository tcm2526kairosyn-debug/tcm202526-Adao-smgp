from sqlalchemy import text


def run_migrations(db):
    """Apply incremental schema changes without Alembic."""
    with db.engine.connect() as conn:
        # MEB, soft-delete
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"
        ))
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS inactive_date TIMESTAMP"
        ))

        # TEB, soft-delete
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"
        ))
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS inactive_date TIMESTAMP"
        ))

        # MEB, SCD Type-2 audit columns
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

        # TEB, SCD Type-2 audit columns
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

        # MCDMWeights, SCD Type-2 audit columns
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

        # Projetos, widen equipa_projeto to TEXT for JSON storage
        conn.execute(text(
            "ALTER TABLE projetos ALTER COLUMN equipa_projeto TYPE TEXT"
        ))

        # MEB, spec-aligned posture coordinates {1,2,3,4}
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS ag_posture INTEGER DEFAULT 2"
        ))
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS as_posture INTEGER DEFAULT 2"
        ))

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

        # TEB, spec-aligned context coordinates {1,2,3,4}
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS agility_support INTEGER DEFAULT 2"
        ))
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS assurance_support INTEGER DEFAULT 2"
        ))

        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS score_traceability FLOAT DEFAULT 0.5"
        ))
        conn.execute(text(
            "ALTER TABLE tool_evidence_base "
            "ADD COLUMN IF NOT EXISTS score_flow_support FLOAT DEFAULT 0.5"
        ))

        for col in ('min_agpi', 'max_aspi', 'score_flexibility',
                    'score_traceability', 'score_speed', 'score_risk_control',
                    'score_stakeholder_eng'):
            conn.execute(text(
                f"ALTER TABLE methodology_evidence_base DROP COLUMN IF EXISTS {col}"
            ))

        for col in ('requires_cloud', 'score_ease_of_use', 'score_reporting', 'score_scalability'):
            conn.execute(text(
                f"ALTER TABLE tool_evidence_base DROP COLUMN IF EXISTS {col}"
            ))

        # TEB, convert category from VARCHAR to JSON array (multi-category support)
        conn.execute(text("""
            ALTER TABLE tool_evidence_base
            ALTER COLUMN category TYPE JSON
            USING CASE
                WHEN category IS NULL THEN '[]'::json
                WHEN category::text LIKE '[%' THEN category::json
                ELSE json_build_array(category)
            END
        """))

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

        for col in ('score_c1_responsiveness', 'score_c2_alignment', 'score_c3_traceability',
                    'score_c4_compliance', 'score_c5_pace_criticality',
                    'score_c6_integration_risk', 'score_c7_distributed_support'):
            conn.execute(text(
                f"ALTER TABLE methodology_evidence_base ADD COLUMN IF NOT EXISTS {col} FLOAT DEFAULT 0.5"
            ))

        for col in ('score_assurance', 'score_agility', 'score_scalability', 'score_hybridisation'):
            conn.execute(text(
                f"ALTER TABLE methodology_evidence_base DROP COLUMN IF EXISTS {col}"
            ))

        for col in ('contribution_cd1', 'contribution_cd2', 'contribution_cd3', 'contribution_cd4',
                    'contribution_cd5', 'contribution_cd6', 'contribution_cd7', 'contribution_cd8'):
            conn.execute(text(
                f"ALTER TABLE tool_evidence_base ADD COLUMN IF NOT EXISTS {col} FLOAT DEFAULT 0.5"
            ))

        for col in ('score_traceability', 'score_integration', 'score_flow_support'):
            conn.execute(text(
                f"ALTER TABLE tool_evidence_base DROP COLUMN IF EXISTS {col}"
            ))

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

        conn.execute(text(
            "ALTER TABLE project_decision "
            "ADD COLUMN IF NOT EXISTS meb_exclusions JSON"
        ))
        conn.execute(text(
            "ALTER TABLE project_decision "
            "ADD COLUMN IF NOT EXISTS teb_exclusions JSON"
        ))

        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS compatible_as_component_of JSON"
        ))
        conn.execute(text(
            "ALTER TABLE project_decision "
            "ADD COLUMN IF NOT EXISTS methodological_envelope JSON"
        ))

        # Stage 4 Level A output: capability_map (cobertura CD1-CD8 por I_A)
        conn.execute(text(
            "ALTER TABLE project_decision "
            "ADD COLUMN IF NOT EXISTS capability_map JSON"
        ))
        for col in ('meb_weights', 'teb_weights', 'portfolio_capability_map'):
            conn.execute(text(
                f"ALTER TABLE project_decision ADD COLUMN IF NOT EXISTS {col} JSON"
            ))

        for col in ('posture_adpo_min', 'posture_adpo_max', 'posture_aspo_min', 'posture_aspo_max'):
            conn.execute(text(
                f"ALTER TABLE methodology_evidence_base ADD COLUMN IF NOT EXISTS {col} INTEGER DEFAULT 2"
            ))
        conn.execute(text(
            "ALTER TABLE methodology_evidence_base "
            "ADD COLUMN IF NOT EXISTS compatible_approaches JSON"
        ))
        # Back-fill regions from the old point columns before dropping them
        conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='methodology_evidence_base' AND column_name='ag_posture'
                ) THEN
                    UPDATE methodology_evidence_base
                    SET posture_adpo_min = ag_posture, posture_adpo_max = ag_posture,
                        posture_aspo_min = as_posture, posture_aspo_max = as_posture;
                    ALTER TABLE methodology_evidence_base DROP COLUMN ag_posture;
                    ALTER TABLE methodology_evidence_base DROP COLUMN as_posture;
                END IF;
            END $$;
        """))

        conn.execute(text("""
            UPDATE project_decision
            SET decision_control_register = jsonb_build_object(
                'binding_constraints', COALESCE(decision_control_register::jsonb->'hard', '[]'::jsonb),
                'acceptance_thresholds', COALESCE(decision_control_register::jsonb->'threshold', '[]'::jsonb),
                'advisory_guidelines', COALESCE(decision_control_register::jsonb->'soft', '[]'::jsonb)
            )::json
            WHERE decision_control_register IS NOT NULL
              AND decision_control_register::jsonb ? 'hard'
        """))

        conn.commit()
