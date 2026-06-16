CREATE TABLE IF NOT EXISTS entity (
  entity_id TEXT PRIMARY KEY,            -- slug, e.g. 'iron', 'warfarin'
  canonical_name TEXT NOT NULL,
  entity_type TEXT NOT NULL,             -- supplement | drug | drug_class | food
  aka TEXT,                              -- JSON array of synonyms
  rxnorm_rxcui TEXT,
  category TEXT,
  dose_low REAL, dose_high REAL, dose_unit TEXT,
  forms TEXT,                            -- JSON array
  dose_source TEXT
);

CREATE TABLE IF NOT EXISTS entity_mechanism (
  entity_id TEXT NOT NULL REFERENCES entity(entity_id),
  tag TEXT NOT NULL,                     -- mechanism tag code
  role TEXT NOT NULL,                    -- substrate|inhibitor|inducer|effector|depletes|susceptible
  dose_threshold REAL, dose_unit TEXT,
  note TEXT
);

CREATE TABLE IF NOT EXISTS interaction_pair (
  rule_id TEXT PRIMARY KEY,
  agent_a TEXT NOT NULL REFERENCES entity(entity_id),
  agent_b TEXT NOT NULL REFERENCES entity(entity_id),
  interaction_type TEXT NOT NULL,        -- chelation-absorption|pk-enzyme|pd-additive|nutrient-depletion|timing-spacing
  severity TEXT NOT NULL,                -- contraindicated|major|moderate|minor|timing-only
  mechanism TEXT,
  is_true_contraindication INTEGER,      -- 0/1
  spacing_hours INTEGER,                 -- for timing-only
  dose_threshold_a REAL, dose_threshold_b REAL, dose_unit TEXT,
  evidence_grade TEXT,                   -- A|B|C|D|F
  evidence_type TEXT,                    -- RCT|meta-analysis|cohort|case-control|case-report|mechanism
  source_name TEXT NOT NULL,
  source_ref TEXT NOT NULL,              -- URL or citation (REQUIRED)
  management_text TEXT
);

CREATE TABLE IF NOT EXISTS additive_rule (
  agg_id TEXT PRIMARY KEY,
  mechanism_class TEXT NOT NULL,         -- e.g. 'anticoagulant'
  secondary_class TEXT,                  -- optional second class counted with mechanism_class (e.g. antiplatelet)
  count_threshold INTEGER NOT NULL,
  requires_rx_anchor INTEGER,            -- 0/1: must include >=1 prescription drug
  escalation_map TEXT NOT NULL,          -- JSON {"2":"major","3":"contraindicated"}
  evidence_grade TEXT, source_name TEXT, source_ref TEXT, management_text TEXT
);

CREATE TABLE IF NOT EXISTS conditional_modifier (
  mod_id TEXT PRIMARY KEY,
  condition TEXT NOT NULL,               -- pregnant|breastfeeding|renal_impaired|hepatic_impaired|hypertension|arrhythmia|pre_surgery|elderly|smoker
  applies_to_mechanism TEXT NOT NULL,    -- mechanism tag or entity_id
  severity_delta INTEGER,                -- +1 / +2 severity levels
  hard_block INTEGER,                    -- 0/1
  source_name TEXT, source_ref TEXT, message_text TEXT
);

CREATE TABLE IF NOT EXISTS survey_rule (
  sr_id TEXT PRIMARY KEY,
  trigger_field TEXT NOT NULL,           -- e.g. 'alcohol','diet','goal','med'
  trigger_value TEXT NOT NULL,
  action TEXT NOT NULL,                  -- recommend|suppress|gate|space
  target_entity TEXT,                    -- entity_id
  gating_flag TEXT,
  rationale TEXT, evidence_grade TEXT, source_ref TEXT
);

CREATE INDEX IF NOT EXISTS idx_mech_entity ON entity_mechanism(entity_id);
CREATE INDEX IF NOT EXISTS idx_pair_a ON interaction_pair(agent_a);
CREATE INDEX IF NOT EXISTS idx_pair_b ON interaction_pair(agent_b);
CREATE INDEX IF NOT EXISTS idx_survey_trigger ON survey_rule(trigger_field, trigger_value);
