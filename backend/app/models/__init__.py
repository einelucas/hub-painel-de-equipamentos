"""Modelos compartilhados pela base do Painel de Equipamentos."""

from app.models.access import UserUnitAccess
from app.models.audit import AuditLog
from app.models.equipment import (
    Area,
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
from app.models.monday_import import (
    ExternalMapping,
    MondayImportBatch,
    MondayImportIssue,
    MondayImportRecord,
    MondayMigrationRun,
)
from app.models.notification import NotificationEvent
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
    "AuditLog",
    "Area",
    "Comment",
    "Contract",
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
    "MondayMigrationRun",
    "Negotiation",
    "NotificationEvent",
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
    "WorkflowException",
    "WorkflowTransition",
    "WorkPackage",
    "Account",
    "Role",
    "Session",
    "User",
    "Verification",
]
