import React, { useState } from "react";
import { Button } from "./ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Badge } from "./ui/badge";
import { ScrollArea } from "./ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { ProcessedEvent } from "./ActivityTimeline";
import {
    Plus,
    Search,
    FileText,
    Calendar,
    MapPin,
    User,
    Clock,
    CheckCircle,
    AlertCircle,
    Building,
    Zap
} from "lucide-react";

interface Project {
    id: string;
    name: string;
    address: string;
    customer: string;
    status: 'planning' | 'investigation' | 'approved' | 'in-progress' | 'completed';
    createdAt: string;
    type: 'residential' | 'commercial' | 'industrial';
}

interface Investigation {
    id: string;
    projectId: string;
    title: string;
    summary: string;
    findings: string[];
    recommendations: string[];
    status: 'completed' | 'in-progress' | 'failed';
    createdAt: string;
    processedEvents: ProcessedEvent[];
    aiResponse?: string;
}

interface WorkOrder {
    id: string;
    projectId: string;
    title: string;
    description: string;
    tasks: string[];
    timeline: string;
    status: 'draft' | 'approved' | 'in-progress' | 'completed';
    createdAt: string;
}

interface DashboardProps {
    onStartNewInvestigation: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onStartNewInvestigation }) => {
    const [selectedTab, setSelectedTab] = useState("investigations");

    // Mock data - in real app, this would come from your backend
    const projects: Project[] = [
        {
            id: "1",
            name: "Smith Residence Solar",
            address: "123 Oak Street, Sacramento, CA",
            customer: "John Smith",
            status: "completed",
            createdAt: "2025-06-08",
            type: "residential"
        },
        {
            id: "2",
            name: "TechCorp Building Solar",
            address: "456 Business Ave, San Francisco, CA",
            customer: "TechCorp Inc",
            status: "in-progress",
            createdAt: "2025-06-09",
            type: "commercial"
        },
        {
            id: "3",
            name: "Greenfield Community Solar",
            address: "789 Solar Way, Fresno, CA",
            customer: "Greenfield Community",
            status: "investigation",
            createdAt: "2025-06-10",
            type: "residential"
        }
    ];

    const investigations: Investigation[] = [
        {
            id: "inv-1",
            projectId: "1",
            title: "Roof Assessment & Permit Analysis",
            summary: "Comprehensive analysis of roof condition, structural integrity, and local permit requirements for 15kW residential solar installation.",
            findings: [
                "Roof is in excellent condition with south-facing orientation",
                "No structural modifications required",
                "Local permits can be expedited due to standard installation",
                "Net metering agreement favorable with 1:1 credit ratio"
            ],
            recommendations: [
                "Recommend 15kW system with 42 panels",
                "Install micro-inverters for optimal performance",
                "Schedule installation during dry season (July-September)",
                "Apply for permits immediately to avoid summer rush"
            ],
            status: "completed",
            createdAt: "2025-06-08T10:30:00Z",
            processedEvents: [
                { title: "Generating Search Queries", data: "roof condition, solar permits Sacramento, net metering California" },
                { title: "Web Research", data: "Gathered 15 sources about Sacramento solar regulations" },
                { title: "Reflection", data: "Need more info about structural requirements" },
                { title: "Web Research", data: "Gathered 8 additional sources about roof load calculations" },
                { title: "Finalizing Answer", data: "Composing comprehensive analysis report" }
            ],
            aiResponse: "Based on my comprehensive analysis of the Smith residence solar project, I've found excellent conditions for installation..."
        },
        {
            id: "inv-2",
            projectId: "2",
            title: "Commercial Solar Feasibility Study",
            summary: "Large-scale commercial installation analysis including grid integration, tax incentives, and ROI calculations.",
            findings: [
                "Building can support 500kW installation",
                "Federal tax credits available (30% ITC)",
                "SGIP rebates available for battery storage",
                "Estimated 7.2 year payback period"
            ],
            recommendations: [
                "Install 500kW system with 1,200 panels",
                "Include 200kWh battery storage system",
                "Consider power purchase agreement (PPA) option",
                "Phase installation over 6 months to minimize disruption"
            ],
            status: "completed",
            createdAt: "2025-06-09T14:15:00Z",
            processedEvents: [
                { title: "Generating Search Queries", data: "commercial solar California, SGIP rebates, solar tax incentives 2025" },
                { title: "Web Research", data: "Gathered 23 sources about commercial solar regulations and incentives" },
                { title: "Finalizing Answer", data: "Calculating ROI and creating feasibility report" }
            ],
            aiResponse: "The commercial solar installation for TechCorp presents an excellent investment opportunity..."
        }
    ];

    const workOrders: WorkOrder[] = [
        {
            id: "wo-1",
            projectId: "1",
            title: "Smith Residence - Solar Installation",
            description: "Complete residential solar installation including panels, inverters, and electrical work",
            tasks: [
                "Site preparation and safety setup",
                "Install mounting rails and hardware",
                "Mount solar panels (42 units)",
                "Install micro-inverters and DC wiring",
                "AC electrical connections and production meter",
                "System commissioning and testing",
                "Final inspection and PTO application"
            ],
            timeline: "5 business days",
            status: "approved",
            createdAt: "2025-06-08T16:45:00Z"
        },
        {
            id: "wo-2",
            projectId: "2",
            title: "TechCorp Building - Phase 1 Installation",
            description: "First phase of commercial solar installation (250kW)",
            tasks: [
                "Engineering site survey",
                "Structural reinforcement (if needed)",
                "Install ballasted mounting system",
                "Install 600 solar panels (Phase 1)",
                "Central inverter installation",
                "AC collection system and transformer",
                "Grid interconnection setup",
                "Monitoring system installation"
            ],
            timeline: "3 weeks",
            status: "in-progress",
            createdAt: "2025-06-09T09:20:00Z"
        }
    ];

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'completed': return 'bg-green-600 text-green-100';
            case 'approved': return 'bg-blue-600 text-blue-100';
            case 'in-progress': return 'bg-orange-600 text-orange-100';
            case 'investigation': return 'bg-yellow-600 text-yellow-100';
            case 'planning': return 'bg-purple-600 text-purple-100';
            case 'failed': return 'bg-red-600 text-red-100';
            case 'draft': return 'bg-gray-600 text-gray-100';
            default: return 'bg-gray-600 text-gray-100';
        }
    };

    const getProjectIcon = (type: string) => {
        switch (type) {
            case 'residential': return <Building className="h-4 w-4" />;
            case 'commercial': return <Building className="h-4 w-4" />;
            case 'industrial': return <Zap className="h-4 w-4" />;
            default: return <Building className="h-4 w-4" />;
        }
    };

    return (
        <div className="w-full min-h-screen bg-white text-gray-900">
            {/* Header */}
            <div className="border-b border-gray-200 bg-white/95 backdrop-blur-sm shadow-sm">
                <div className="container mx-auto px-4 py-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-2xl font-bold text-gray-900">☀️ Solar Investigator Dashboard</h1>
                            <p className="text-gray-600">AI-powered solar project management and analysis</p>
                        </div>
                        <Button
                            onClick={onStartNewInvestigation}
                            className="bg-blue-600 hover:bg-blue-700 text-white shadow-md"
                        >
                            <Plus className="h-4 w-4 mr-2" />
                            New Investigation
                        </Button>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="container mx-auto px-4 py-6">
                <Tabs value={selectedTab} onValueChange={setSelectedTab} className="w-full">
                    <TabsList className="grid w-full grid-cols-3 mb-6 bg-gray-100 h-12">
                        <TabsTrigger
                            value="investigations"
                            className="data-[state=active]:bg-white data-[state=active]:shadow-sm flex items-center justify-center gap-2 text-sm font-medium h-full"
                        >
                            <Search className="h-4 w-4" />
                            Investigations
                        </TabsTrigger>
                        <TabsTrigger
                            value="workorders"
                            className="data-[state=active]:bg-white data-[state=active]:shadow-sm flex items-center justify-center gap-2 text-sm font-medium h-full"
                        >
                            <FileText className="h-4 w-4" />
                            Work Orders
                        </TabsTrigger>
                        <TabsTrigger
                            value="projects"
                            className="data-[state=active]:bg-white data-[state=active]:shadow-sm flex items-center justify-center gap-2 text-sm font-medium h-full"
                        >
                            <Building className="h-4 w-4" />
                            Projects
                        </TabsTrigger>
                    </TabsList>

                    {/* Investigations Tab */}
                    <TabsContent value="investigations" className="space-y-4">
                        <div className="grid gap-4">
                            {investigations.map((investigation) => {
                                const project = projects.find(p => p.id === investigation.projectId);
                                return (
                                    <Card key={investigation.id} className="bg-white border-gray-200 shadow-md hover:shadow-lg transition-shadow">
                                        <CardHeader>
                                            <div className="flex items-start justify-between">
                                                <div>
                                                    <CardTitle className="text-gray-900 flex items-center gap-2">
                                                        <Search className="h-5 w-5 text-blue-600" />
                                                        {investigation.title}
                                                    </CardTitle>
                                                    <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
                                                        <span className="flex items-center gap-1">
                                                            <MapPin className="h-3 w-3" />
                                                            {project?.name}
                                                        </span>
                                                        <span className="flex items-center gap-1">
                                                            <Calendar className="h-3 w-3" />
                                                            {new Date(investigation.createdAt).toLocaleDateString()}
                                                        </span>
                                                    </div>
                                                </div>
                                                <Badge className={getStatusColor(investigation.status)}>
                                                    {investigation.status === 'completed' && <CheckCircle className="h-3 w-3 mr-1" />}
                                                    {investigation.status === 'in-progress' && <Clock className="h-3 w-3 mr-1" />}
                                                    {investigation.status === 'failed' && <AlertCircle className="h-3 w-3 mr-1" />}
                                                    {investigation.status.charAt(0).toUpperCase() + investigation.status.slice(1)}
                                                </Badge>
                                            </div>
                                        </CardHeader>
                                        <CardContent>
                                            <p className="text-gray-700 mb-4">{investigation.summary}</p>

                                            <div className="grid md:grid-cols-2 gap-4 mb-4">
                                                <div>
                                                    <h4 className="font-medium text-gray-800 mb-2">Key Findings</h4>
                                                    <ul className="space-y-1">
                                                        {investigation.findings.slice(0, 3).map((finding, idx) => (
                                                            <li key={idx} className="text-sm text-gray-600 flex items-start gap-2">
                                                                <CheckCircle className="h-3 w-3 mt-0.5 text-green-600 flex-shrink-0" />
                                                                {finding}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                                <div>
                                                    <h4 className="font-medium text-gray-800 mb-2">Recommendations</h4>
                                                    <ul className="space-y-1">
                                                        {investigation.recommendations.slice(0, 3).map((rec, idx) => (
                                                            <li key={idx} className="text-sm text-gray-600 flex items-start gap-2">
                                                                <Zap className="h-3 w-3 mt-0.5 text-blue-600 flex-shrink-0" />
                                                                {rec}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            </div>

                                            <div className="pt-2 border-t border-gray-200">
                                                <p className="text-xs text-gray-500 mb-2">Investigation Steps:</p>
                                                <div className="flex flex-wrap gap-2">
                                                    {investigation.processedEvents.map((event, idx) => (
                                                        <Badge key={idx} variant="outline" className="text-xs border-gray-300 text-gray-600">
                                                            {event.title}
                                                        </Badge>
                                                    ))}
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                );
                            })}
                        </div>
                    </TabsContent>

                    {/* Work Orders Tab */}
                    <TabsContent value="workorders" className="space-y-4">
                        <div className="grid gap-4">
                            {workOrders.map((workOrder) => {
                                const project = projects.find(p => p.id === workOrder.projectId);
                                return (
                                    <Card key={workOrder.id} className="bg-white border-gray-200 shadow-md hover:shadow-lg transition-shadow">
                                        <CardHeader>
                                            <div className="flex items-start justify-between">
                                                <div>
                                                    <CardTitle className="text-gray-900 flex items-center gap-2">
                                                        <FileText className="h-5 w-5 text-green-600" />
                                                        {workOrder.title}
                                                    </CardTitle>
                                                    <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
                                                        <span className="flex items-center gap-1">
                                                            <MapPin className="h-3 w-3" />
                                                            {project?.name}
                                                        </span>
                                                        <span className="flex items-center gap-1">
                                                            <Clock className="h-3 w-3" />
                                                            {workOrder.timeline}
                                                        </span>
                                                        <span className="flex items-center gap-1">
                                                            <Calendar className="h-3 w-3" />
                                                            {new Date(workOrder.createdAt).toLocaleDateString()}
                                                        </span>
                                                    </div>
                                                </div>
                                                <Badge className={getStatusColor(workOrder.status)}>
                                                    {workOrder.status.charAt(0).toUpperCase() + workOrder.status.slice(1)}
                                                </Badge>
                                            </div>
                                        </CardHeader>
                                        <CardContent>
                                            <p className="text-gray-700 mb-4">{workOrder.description}</p>

                                            <div>
                                                <h4 className="font-medium text-gray-800 mb-2">Task List</h4>
                                                <ScrollArea className="h-32">
                                                    <ul className="space-y-2">
                                                        {workOrder.tasks.map((task, idx) => (
                                                            <li key={idx} className="text-sm text-gray-600 flex items-start gap-2">
                                                                <CheckCircle className="h-3 w-3 mt-0.5 text-green-600 flex-shrink-0" />
                                                                {task}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </ScrollArea>
                                            </div>
                                        </CardContent>
                                    </Card>
                                );
                            })}
                        </div>
                    </TabsContent>

                    {/* Projects Tab */}
                    <TabsContent value="projects" className="space-y-4">
                        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                            {projects.map((project) => (
                                <Card key={project.id} className="bg-white border-gray-200 shadow-md hover:shadow-lg transition-shadow">
                                    <CardHeader>
                                        <div className="flex items-start justify-between">
                                            <div>
                                                <CardTitle className="text-gray-900 flex items-center gap-2 text-lg">
                                                    {getProjectIcon(project.type)}
                                                    {project.name}
                                                </CardTitle>
                                                <div className="flex items-center gap-2 mt-2 text-sm text-gray-600">
                                                    <User className="h-3 w-3" />
                                                    {project.customer}
                                                </div>
                                            </div>
                                            <Badge className={getStatusColor(project.status)}>
                                                {project.status.charAt(0).toUpperCase() + project.status.slice(1)}
                                            </Badge>
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-2 text-sm">
                                            <div className="flex items-start gap-2 text-gray-600">
                                                <MapPin className="h-3 w-3 mt-0.5 flex-shrink-0" />
                                                {project.address}
                                            </div>
                                            <div className="flex items-center gap-2 text-gray-600">
                                                <Calendar className="h-3 w-3" />
                                                Created {new Date(project.createdAt).toLocaleDateString()}
                                            </div>
                                            <div className="flex items-center gap-2 text-gray-600">
                                                <Building className="h-3 w-3" />
                                                {project.type.charAt(0).toUpperCase() + project.type.slice(1)} Project
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    );
};
