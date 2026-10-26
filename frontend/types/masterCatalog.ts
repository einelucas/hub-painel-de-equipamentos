export interface MasterArea {
  id: string;
  name: string;
  isUnassigned: boolean;
  active: boolean;
}

export interface MasterComponent {
  id: string;
  name: string;
  active: boolean;
}

export interface MasterEquipment {
  id: string;
  name: string;
  areaIds: string[];
  components: MasterComponent[];
  active: boolean;
  reviewFlags: string[];
}

export interface MasterCatalog {
  areas: MasterArea[];
  equipments: MasterEquipment[];
}

export interface MasterCatalogSeedResult {
  areasNew: number;
  equipmentsNew: number;
  componentsNew: number;
  existing: number;
  dryRun: boolean;
}

export type MasterCatalogRecordKind = "equipamento" | "componente" | "área";

export interface MasterCatalogRenameTarget {
  path: string;
  previous: string;
  kind: MasterCatalogRecordKind;
  maxLength: number;
}
