"""Modelos compartilhados pela base do Painel de Equipamentos."""

from app.models.access import UserModuleContextPreference, UserUnitAccess
from app.models.audit import AuditLog
from app.models.equipment import (
    Area,
    CriticalityLabel,
    Discipline,
    EapNode,
    Equipment,
    EquipmentComponent,
    EquipmentWorkPackage,
    ProjectContext,
    ProjectEap,
    Unit,
    WorkflowTransition,
    WorkPackage,
)
from app.models.master_catalog import (
    MasterArea,
    MasterComponentOption,
    MasterEquipment,
    MasterEquipmentArea,
    MasterProjectCreation,
)
from app.models.monday_import import (
    ExternalMapping,
    MondayApplyJob,
    MondayImportBatch,
    MondayImportIssue,
    MondayImportRecord,
    MondayMigrationRun,
)
from app.models.notification import (
    EmailDelivery,
    EmailTemplate,
    NotificationEvent,
    NotificationRule,
)
from app.models.process import (
    Contract,
    LegalProcess,
    Negotiation,
    PurchaseOrder,
    PurchaseRequest,
)
from app.models.supplier import (
    EquipmentSupplier,
    Supplier,
    SupplierAlias,
    SupplierRecommendationEvidence,
)
from app.models.user import Account, Role, Session, User, Verification
from app.models.workflow_extras import (
    Comment,
    OperationalStatusEvent,
    ReopenRequest,
    RequirementWaiver,
    WorkflowException,
)

__all__ = [
    "MasterArea", "MasterComponentOption", "MasterEquipment", "MasterEquipmentArea",
    "MasterProjectCreation",
    "AuditLog",
    "Area",
    "Comment",
    "Contract",
    "CriticalityLabel",
    "Discipline",
    "EapNode",
    "Equipment",
    "EquipmentComponent",
    "EquipmentSupplier",
    "EquipmentWorkPackage",
    "ExternalMapping",
    "LegalProcess",
    "MondayImportBatch",
    "MondayImportIssue",
    "MondayImportRecord",
    "MondayApplyJob",
    "MondayMigrationRun",
    "Negotiation",
    "NotificationEvent",
    "NotificationRule",
    "EmailDelivery",
    "EmailTemplate",
    "OperationalStatusEvent",
    "ProjectContext",
    "ProjectEap",
    "PurchaseOrder",
    "PurchaseRequest",
    "ReopenRequest",
    "RequirementWaiver",
    "Supplier",
    "SupplierAlias",
    "SupplierRecommendationEvidence",
    "Unit",
    "UserUnitAccess",
    "UserModuleContextPreference",
    "WorkflowException",
    "WorkflowTransition",
    "WorkPackage",
    "Account",
    "Role",
    "Session",
    "User",
    "Verification",
]
