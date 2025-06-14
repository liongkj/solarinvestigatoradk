"""Mock data service for the Solar Investigator API."""

from typing import List, Optional, Dict
from .models import Project, Investigation, WorkOrder, ProcessedEvent, DashboardSummary


class MockDataService:
    """Service class for managing mock data."""

    def __init__(self):
        """Initialize the mock data service with sample data."""
        self._projects = self._get_sample_projects()
        self._investigations = self._get_sample_investigations()
        self._work_orders = self._get_sample_work_orders()

    def _get_sample_projects(self) -> List[Project]:
        """Get sample projects data."""
        return [
            Project(
                id="1",
                name="Smith Residence Solar",
                address="123 Oak Street, Sacramento, CA",
                customer="John Smith",
                status="completed",
                createdAt="2025-06-08",
                type="residential",
            ),
            Project(
                id="2",
                name="TechCorp Building Solar",
                address="456 Business Ave, San Francisco, CA",
                customer="TechCorp Inc",
                status="in-progress",
                createdAt="2025-06-09",
                type="commercial",
            ),
            Project(
                id="3",
                name="Greenfield Community Solar",
                address="789 Solar Way, Fresno, CA",
                customer="Greenfield Community",
                status="investigation",
                createdAt="2025-06-10",
                type="residential",
            ),
        ]

    def _get_sample_investigations(self) -> List[Investigation]:
        """Get sample investigations data."""
        return [
            Investigation(
                id="inv-1",
                projectId="1",
                title="Roof Assessment & Permit Analysis",
                summary="Comprehensive analysis of roof condition, structural integrity, and local permit requirements for 15kW residential solar installation.",
                findings=[
                    "Roof is in excellent condition with south-facing orientation",
                    "No structural modifications required",
                    "Local permits can be expedited due to standard installation",
                    "Net metering agreement favorable with 1:1 credit ratio",
                ],
                recommendations=[
                    "Recommend 15kW system with 42 panels",
                    "Install micro-inverters for optimal performance",
                    "Schedule installation during dry season (July-September)",
                    "Apply for permits immediately to avoid summer rush",
                ],
                status="completed",
                createdAt="2025-06-08T10:30:00Z",
                processedEvents=[
                    ProcessedEvent(
                        title="Generating Search Queries",
                        data="roof condition, solar permits Sacramento, net metering California",
                    ),
                    ProcessedEvent(
                        title="Web Research",
                        data="Gathered 15 sources about Sacramento solar regulations",
                    ),
                    ProcessedEvent(
                        title="Reflection",
                        data="Need more info about structural requirements",
                    ),
                    ProcessedEvent(
                        title="Web Research",
                        data="Gathered 8 additional sources about roof load calculations",
                    ),
                    ProcessedEvent(
                        title="Finalizing Answer",
                        data="Composing comprehensive analysis report",
                    ),
                ],
                aiResponse="Based on my comprehensive analysis of the Smith residence solar project, I've found excellent conditions for installation...",
            ),
            Investigation(
                id="inv-2",
                projectId="2",
                title="Commercial Solar Feasibility Study",
                summary="Large-scale commercial installation analysis including grid integration, tax incentives, and ROI calculations.",
                findings=[
                    "Building can support 500kW installation",
                    "Federal tax credits available (30% ITC)",
                    "SGIP rebates available for battery storage",
                    "Estimated 7.2 year payback period",
                ],
                recommendations=[
                    "Install 500kW system with 1,200 panels",
                    "Include 200kWh battery storage system",
                    "Consider power purchase agreement (PPA) option",
                    "Phase installation over 6 months to minimize disruption",
                ],
                status="completed",
                createdAt="2025-06-09T14:15:00Z",
                processedEvents=[
                    ProcessedEvent(
                        title="Generating Search Queries",
                        data="commercial solar California, SGIP rebates, solar tax incentives 2025",
                    ),
                    ProcessedEvent(
                        title="Web Research",
                        data="Gathered 23 sources about commercial solar regulations and incentives",
                    ),
                    ProcessedEvent(
                        title="Finalizing Answer",
                        data="Calculating ROI and creating feasibility report",
                    ),
                ],
                aiResponse="The commercial solar installation for TechCorp presents an excellent investment opportunity...",
            ),
        ]

    def _get_sample_work_orders(self) -> List[WorkOrder]:
        """Get sample work orders data."""
        return [
            WorkOrder(
                id="wo-1",
                projectId="1",
                title="Smith Residence - Solar Installation",
                description="Complete residential solar installation including panels, inverters, and electrical work",
                tasks=[
                    "Site preparation and safety setup",
                    "Install mounting rails and hardware",
                    "Mount solar panels (42 units)",
                    "Install micro-inverters and DC wiring",
                    "AC electrical connections and production meter",
                    "System commissioning and testing",
                    "Final inspection and PTO application",
                ],
                timeline="5 business days",
                status="approved",
                createdAt="2025-06-08T16:45:00Z",
            ),
            WorkOrder(
                id="wo-2",
                projectId="2",
                title="TechCorp Building - Phase 1 Installation",
                description="First phase of commercial solar installation (250kW)",
                tasks=[
                    "Engineering site survey",
                    "Structural reinforcement (if needed)",
                    "Install ballasted mounting system",
                    "Install 600 solar panels (Phase 1)",
                    "Central inverter installation",
                    "AC collection system and transformer",
                    "Grid interconnection setup",
                    "Monitoring system installation",
                ],
                timeline="3 weeks",
                status="in-progress",
                createdAt="2025-06-09T09:20:00Z",
            ),
        ]

    # Projects methods
    def get_all_projects(self) -> List[Project]:
        """Get all projects."""
        return self._projects

    def get_project_by_id(self, project_id: str) -> Optional[Project]:
        """Get a project by ID."""
        return next((p for p in self._projects if p.id == project_id), None)

    def get_projects_by_status(self, status: str) -> List[Project]:
        """Get projects filtered by status."""
        return [p for p in self._projects if p.status == status]

    # Investigations methods
    def get_all_investigations(self) -> List[Investigation]:
        """Get all investigations."""
        return self._investigations

    def get_investigation_by_id(self, investigation_id: str) -> Optional[Investigation]:
        """Get an investigation by ID."""
        return next((i for i in self._investigations if i.id == investigation_id), None)

    def get_investigations_by_project(self, project_id: str) -> List[Investigation]:
        """Get investigations for a specific project."""
        return [i for i in self._investigations if i.projectId == project_id]

    def get_investigations_by_status(self, status: str) -> List[Investigation]:
        """Get investigations filtered by status."""
        return [i for i in self._investigations if i.status == status]

    # Work Orders methods
    def get_all_work_orders(self) -> List[WorkOrder]:
        """Get all work orders."""
        return self._work_orders

    def get_work_order_by_id(self, work_order_id: str) -> Optional[WorkOrder]:
        """Get a work order by ID."""
        return next((w for w in self._work_orders if w.id == work_order_id), None)

    def get_work_orders_by_project(self, project_id: str) -> List[WorkOrder]:
        """Get work orders for a specific project."""
        return [w for w in self._work_orders if w.projectId == project_id]

    def get_work_orders_by_status(self, status: str) -> List[WorkOrder]:
        """Get work orders filtered by status."""
        return [w for w in self._work_orders if w.status == status]

    # Dashboard summary
    def get_dashboard_summary(self) -> DashboardSummary:
        """Get dashboard summary statistics."""
        return DashboardSummary(
            totalProjects=len(self._projects),
            activeInvestigations=len(
                [i for i in self._investigations if i.status == "in-progress"]
            ),
            completedInvestigations=len(
                [i for i in self._investigations if i.status == "completed"]
            ),
            activeWorkOrders=len(
                [
                    w
                    for w in self._work_orders
                    if w.status in ["approved", "in-progress"]
                ]
            ),
            completedWorkOrders=len(
                [w for w in self._work_orders if w.status == "completed"]
            ),
        )


# Global instance
mock_data_service = MockDataService()
