import React, { useState } from "react";
import { InputForm } from "./InputForm";
import { Button } from "./ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "./ui/select";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { ActivityTimeline, ProcessedEvent } from "./ActivityTimeline";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "./ui/dialog";

interface Project {
    id: string;
    name: string;
    address: string;
    customer: string;
    status: 'planning' | 'investigation' | 'approved' | 'in-progress' | 'completed';
    type: 'residential' | 'commercial' | 'industrial';
}

interface InvestigationDialogProps {
    isOpen: boolean;
    onClose: () => void;
    handleSubmit: (
        submittedInputValue: string,
        effort: string,
        model: string
    ) => void;
    onCancel: () => void;
    isLoading: boolean;
    processedEvents?: ProcessedEvent[];
}

export const InvestigationDialog: React.FC<InvestigationDialogProps> = ({
    isOpen,
    onClose,
    handleSubmit,
    onCancel,
    isLoading,
    processedEvents = [],
}) => {
    const [selectedProject, setSelectedProject] = useState<string>("");
    const [showCustomQuery, setShowCustomQuery] = useState(false);

    // Mock projects - in real app, this would come from your backend
    const projects: Project[] = [
        {
            id: "1",
            name: "Residential Solar - Smith House",
            address: "123 Oak Street, Sacramento, CA",
            customer: "John Smith",
            status: "planning",
            type: "residential"
        },
        {
            id: "2",
            name: "Commercial Solar - TechCorp Building",
            address: "456 Business Ave, San Francisco, CA",
            customer: "TechCorp Inc",
            status: "investigation",
            type: "commercial"
        },
        {
            id: "3",
            name: "Community Solar - Greenfield Development",
            address: "789 Solar Way, Fresno, CA",
            customer: "Greenfield Community",
            status: "planning",
            type: "residential"
        }
    ];

    const handleStartInvestigation = () => {
        if (!selectedProject) {
            alert("Please select a project first");
            return;
        }

        const project = projects.find(p => p.id === selectedProject);
        if (project) {
            const investigationQuery = `Conduct a comprehensive solar installation investigation for: ${project.name} at ${project.address}. 

      Please analyze the following aspects:
      1. Roof conditions and structural integrity
      2. Local building codes and permit requirements  
      3. Electrical system compatibility and grid interconnection
      4. Weather patterns and solar irradiance data
      5. Available incentives, rebates, and financing options
      6. Regulatory compliance and utility requirements
      7. Timeline and installation considerations
      8. Cost analysis and ROI projections

      Provide detailed findings and actionable recommendations for this ${project.type} solar project.`;

            handleSubmit(investigationQuery, "thorough", "gemini-2.0-flash-exp");
        }
    };

    const handleCreateWorkOrder = () => {
        if (!selectedProject) {
            alert("Please select a project first");
            return;
        }

        const project = projects.find(p => p.id === selectedProject);
        if (project) {
            const workOrderQuery = `Create a detailed work order for solar installation at ${project.name}, ${project.address}. 

      Please include:
      1. Pre-installation checklist and site preparation requirements
      2. Detailed step-by-step installation procedures
      3. Required equipment, materials, and tools list
      4. Personnel requirements and crew assignments
      5. Safety protocols and requirements
      6. Quality control checkpoints and testing procedures
      7. Timeline with milestones and dependencies
      8. Post-installation commissioning and documentation requirements
      9. Customer handover procedures and training requirements
      10. Warranty and maintenance schedule

      Format this as a comprehensive work order ready for field teams to execute for this ${project.type} installation.`;

            handleSubmit(workOrderQuery, "thorough", "gemini-2.0-flash-exp");
        }
    };

    const handleDialogClose = () => {
        setSelectedProject("");
        setShowCustomQuery(false);
        onClose();
    };

    if (showCustomQuery) {
        return (
            <Dialog open={isOpen} onOpenChange={handleDialogClose}>
                <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-white text-gray-900 border-gray-200">
                    <DialogHeader>
                        <DialogTitle className="text-gray-900">Custom Investigation</DialogTitle>
                        <DialogDescription className="text-gray-600">
                            Enter a custom query for your solar investigation
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-6">
                        <Button
                            variant="ghost"
                            onClick={() => setShowCustomQuery(false)}
                            className="text-gray-600 hover:text-gray-900 hover:bg-gray-100"
                        >
                            ← Back to Project Selection
                        </Button>

                        <div className="w-full">
                            <InputForm
                                onSubmit={handleSubmit}
                                isLoading={isLoading}
                                onCancel={onCancel}
                                hasHistory={false}
                            />
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        );
    }

    return (
        <Dialog open={isOpen} onOpenChange={handleDialogClose}>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-white text-gray-900 border-gray-200">
                <DialogHeader>
                    <DialogTitle className="text-gray-900 text-2xl">☀️ Start Investigation</DialogTitle>
                    <DialogDescription className="text-gray-600">
                        AI-powered solar project analysis and work order generation
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-6">
                    {/* Show investigation progress if there are events or if loading after starting investigation */}
                    {(processedEvents.length > 0 || (isLoading && selectedProject)) && (
                        <div className="w-full">
                            <ActivityTimeline
                                processedEvents={processedEvents}
                                isLoading={isLoading}
                            />
                        </div>
                    )}

                    <Card className="w-full bg-white border-gray-200 shadow-lg">
                        <CardHeader>
                            <CardTitle className="text-gray-900">Select Project</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <Select value={selectedProject} onValueChange={setSelectedProject}>
                                <SelectTrigger className="w-full bg-gray-50 border-gray-300 text-gray-900 hover:bg-gray-100">
                                    <SelectValue placeholder="Choose a solar project..." />
                                </SelectTrigger>
                                <SelectContent className="bg-white border-gray-200">
                                    {projects.map((project) => (
                                        <SelectItem
                                            key={project.id}
                                            value={project.id}
                                            className="text-gray-900 focus:bg-gray-100"
                                        >
                                            <div className="flex flex-col items-start">
                                                <span className="font-medium">{project.name}</span>
                                                <span className="text-sm text-gray-600">{project.address}</span>
                                                <span className="text-xs text-gray-500">Customer: {project.customer}</span>
                                            </div>
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            {selectedProject && (
                                <div className="p-4 bg-gray-50 rounded-lg text-left border">
                                    {(() => {
                                        const project = projects.find(p => p.id === selectedProject);
                                        return project ? (
                                            <div>
                                                <h3 className="font-medium text-gray-900">{project.name}</h3>
                                                <p className="text-sm text-gray-700 mt-1">{project.address}</p>
                                                <p className="text-sm text-gray-600 mt-1">Customer: {project.customer}</p>
                                                <div className="flex gap-2 mt-3">
                                                    <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${project.status === 'planning' ? 'bg-blue-100 text-blue-800' :
                                                        project.status === 'investigation' ? 'bg-yellow-100 text-yellow-800' :
                                                            project.status === 'approved' ? 'bg-green-100 text-green-800' :
                                                                project.status === 'in-progress' ? 'bg-orange-100 text-orange-800' :
                                                                    'bg-gray-100 text-gray-800'
                                                        }`}>
                                                        {project.status.charAt(0).toUpperCase() + project.status.slice(1)}
                                                    </span>
                                                    <span className="inline-block px-3 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                                                        {project.type.charAt(0).toUpperCase() + project.type.slice(1)}
                                                    </span>
                                                </div>
                                            </div>
                                        ) : null;
                                    })()}
                                </div>
                            )}

                            <div className="flex flex-col sm:flex-row gap-4 pt-4">
                                <Button
                                    onClick={handleStartInvestigation}
                                    disabled={!selectedProject || isLoading}
                                    className="flex-1 bg-blue-600 hover:bg-blue-700 text-white shadow-md"
                                >
                                    🔍 Start Investigation
                                </Button>
                                <Button
                                    onClick={handleCreateWorkOrder}
                                    disabled={!selectedProject || isLoading}
                                    className="flex-1 bg-green-600 hover:bg-green-700 text-white shadow-md"
                                >
                                    📋 Create Work Order
                                </Button>
                            </div>

                            <div className="pt-4 border-t border-gray-200">
                                <Button
                                    variant="outline"
                                    onClick={() => setShowCustomQuery(true)}
                                    className="w-full border-gray-300 text-gray-700 hover:bg-gray-50"
                                >
                                    Custom Investigation Query
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    <p className="text-xs text-gray-500 text-center">
                        Select a project and choose an action. The AI agent will conduct thorough research and provide detailed reports with citations.
                    </p>
                </div>
            </DialogContent>
        </Dialog>
    );
};
