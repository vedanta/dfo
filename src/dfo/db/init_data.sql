-- Initial data for vm_equivalence table
-- Maps legacy Azure VM SKUs to modern equivalents for pricing
-- Reference: docs/azure_vm_selection_strategy.md

-- B-series (Burstable) mappings
INSERT INTO vm_equivalence VALUES
  ('Standard_B1s', 'Standard_B2ls_v2', 1, 2, 1, 4, 'B', 'Burstable compute - closest modern equivalent'),
  ('Standard_B1ms', 'Standard_B2s_v2', 1, 2, 2, 4, 'B', 'Burstable compute - closest CPU/memory ratio'),
  ('Standard_B2s', 'Standard_B2s_v2', 2, 2, 4, 4, 'B', 'Direct v2 replacement'),
  ('Standard_B2ms', 'Standard_B2ms_v2', 2, 2, 8, 8, 'B', 'Direct v2 replacement'),
  ('Standard_B4ms', 'Standard_B4ms_v2', 4, 4, 16, 16, 'B', 'Direct v2 replacement'),
  ('Standard_B8ms', 'Standard_B8ms_v2', 8, 8, 32, 32, 'B', 'Direct v2 replacement');

-- A-series (Deprecated general purpose) → D-series v5
INSERT INTO vm_equivalence VALUES
  ('Standard_A1', 'Standard_D2s_v5', 1, 2, 1.75, 8, 'A->D', 'Legacy general purpose → modern general purpose'),
  ('Standard_A2', 'Standard_D2s_v5', 2, 2, 3.5, 8, 'A->D', 'Legacy general purpose → modern general purpose'),
  ('Standard_A3', 'Standard_D4s_v5', 4, 4, 7, 16, 'A->D', 'Legacy general purpose → modern general purpose'),
  ('Standard_A4', 'Standard_D8s_v5', 8, 8, 14, 32, 'A->D', 'Legacy general purpose → modern general purpose'),
  ('Standard_A1_v2', 'Standard_D2s_v5', 1, 2, 2, 8, 'A->D', 'Legacy general purpose → modern general purpose'),
  ('Standard_A2_v2', 'Standard_D2s_v5', 2, 2, 4, 8, 'A->D', 'Legacy general purpose → modern general purpose'),
  ('Standard_A4_v2', 'Standard_D4s_v5', 4, 4, 8, 16, 'A->D', 'Legacy general purpose → modern general purpose'),
  ('Standard_A8_v2', 'Standard_D8s_v5', 8, 8, 16, 32, 'A->D', 'Legacy general purpose → modern general purpose');

-- D-series legacy → D-series v5
INSERT INTO vm_equivalence VALUES
  ('Standard_D1', 'Standard_D2s_v5', 1, 2, 3.5, 8, 'D', 'Legacy D-series → v5'),
  ('Standard_D2', 'Standard_D2s_v5', 2, 2, 7, 8, 'D', 'Legacy D-series → v5'),
  ('Standard_D3', 'Standard_D4s_v5', 4, 4, 14, 16, 'D', 'Legacy D-series → v5'),
  ('Standard_D4', 'Standard_D8s_v5', 8, 8, 28, 32, 'D', 'Legacy D-series → v5'),
  ('Standard_D1_v2', 'Standard_D2s_v5', 1, 2, 3.5, 8, 'D', 'D-series v2 → v5'),
  ('Standard_D2_v2', 'Standard_D2s_v5', 2, 2, 7, 8, 'D', 'D-series v2 → v5'),
  ('Standard_D3_v2', 'Standard_D4s_v5', 4, 4, 14, 16, 'D', 'D-series v2 → v5'),
  ('Standard_D4_v2', 'Standard_D8s_v5', 8, 8, 28, 32, 'D', 'D-series v2 → v5'),
  ('Standard_D2s_v3', 'Standard_D2s_v5', 2, 2, 8, 8, 'D', 'D-series v3 → v5'),
  ('Standard_D4s_v3', 'Standard_D4s_v5', 4, 4, 16, 16, 'D', 'D-series v3 → v5'),
  ('Standard_D8s_v3', 'Standard_D8s_v5', 8, 8, 32, 32, 'D', 'D-series v3 → v5');

-- E-series (Memory optimized) legacy → E-series v5
INSERT INTO vm_equivalence VALUES
  ('Standard_E2_v3', 'Standard_E2s_v5', 2, 2, 16, 16, 'E', 'E-series v3 → v5'),
  ('Standard_E4_v3', 'Standard_E4s_v5', 4, 4, 32, 32, 'E', 'E-series v3 → v5'),
  ('Standard_E8_v3', 'Standard_E8s_v5', 8, 8, 64, 64, 'E', 'E-series v3 → v5'),
  ('Standard_E16_v3', 'Standard_E16s_v5', 16, 16, 128, 128, 'E', 'E-series v3 → v5');
