import os
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from openai import OpenAI
from langgraph.graph import Graph, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

logger = logging.getLogger(__name__)

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

class AgentState(TypedDict):
    """State shared between agents in the workflow."""
    xml_content: str
    raw_data: Dict[str, Any]
    analyzed_data: Dict[str, Any]
    extracted_data: Dict[str, Any]
    validated_data: Dict[str, Any]
    confidence_score: float
    errors: List[str]
    processing_notes: List[str]
    current_step: str

@dataclass
class ProcessingResult:
    """Result of the AI processing workflow."""
    success: bool
    data: Optional[Dict[str, Any]]
    confidence_score: float
    errors: List[str]
    processing_notes: List[str]

class NFEAnalysisAgent:
    """Agent responsible for analyzing NFe XML structure and content."""
    
    def __init__(self):
        self.name = "NFE_Analysis_Agent"
    
    def analyze(self, state: AgentState) -> AgentState:
        """Analyze the NFe XML structure and identify key sections."""
        logger.info(f"{self.name}: Starting NFe analysis")
        
        try:
            analysis_prompt = """
            You are an expert in Brazilian NFe (Nota Fiscal Eletrônica) XML analysis.
            Analyze the provided NFe XML content and identify:

            1. Document structure and version
            2. Main sections present (IDE, EMIT, DEST, DET, TOTAL, etc.)
            3. Data quality assessment
            4. Any structural issues or missing sections
            5. Complexity assessment for extraction

            Respond with JSON in this format:
            {
                "structure_version": "version_info",
                "sections_identified": ["list", "of", "sections"],
                "data_quality": "high|medium|low",
                "structural_issues": ["list", "of", "issues"],
                "complexity_score": 0.1-1.0,
                "analysis_notes": ["detailed", "notes"]
            }
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": analysis_prompt},
                    {"role": "user", "content": f"Analyze this NFe XML:\n\n{state['xml_content'][:8000]}..."}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            analysis_result = json.loads(response.choices[0].message.content)
            
            state['analyzed_data'] = analysis_result
            state['current_step'] = 'analysis_complete'
            state['processing_notes'].append(f"{self.name}: Analysis completed successfully")
            
            logger.info(f"{self.name}: Analysis completed with complexity score: {analysis_result.get('complexity_score', 0)}")
            
        except Exception as e:
            error_msg = f"{self.name}: Analysis failed - {str(e)}"
            logger.error(error_msg)
            state['errors'].append(error_msg)
            state['current_step'] = 'analysis_failed'
        
        return state

class NFEExtractionAgent:
    """Agent responsible for extracting and classifying NFe data fields."""
    
    def __init__(self):
        self.name = "NFE_Extraction_Agent"
    
    def extract(self, state: AgentState) -> AgentState:
        """Extract and classify all NFe fields using AI."""
        logger.info(f"{self.name}: Starting field extraction")
        
        try:
            extraction_prompt = """
            You are an expert in Brazilian NFe data extraction and classification.
            Extract ALL relevant fields from the NFe XML according to the official structure.

            Focus on these main sections:
            1. IDENTIFICATION (IDE) - document info, dates, operation type
            2. ISSUER (EMIT) - emitter company data and address
            3. RECIPIENT (DEST) - recipient company data and address
            4. ITEMS (DET) - all products/services with detailed tax info
            5. TOTALS (TOTAL) - all financial totals and tax values
            6. TRANSPORT (TRANSP) - shipping and transport info
            7. PAYMENT (PAG) - payment method and terms
            8. PROTOCOL (PROTNFE) - authorization protocol info

            For each field, provide:
            - Field name
            - Extracted value
            - Data type
            - Confidence level (0.0-1.0)
            - Source section in XML

            Respond with JSON in this format:
            {
                "identification": {
                    "field_name": {"value": "extracted_value", "confidence": 0.95, "data_type": "string|number|date"},
                    ...
                },
                "issuer": {...},
                "recipient": {...},
                "items": [
                    {
                        "item_number": {...},
                        "product_code": {...},
                        ...
                    }
                ],
                "totals": {...},
                "transport": {...},
                "payment": {...},
                "protocol": {...},
                "overall_confidence": 0.0-1.0,
                "extraction_notes": ["detailed", "notes"]
            }
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": extraction_prompt},
                    {"role": "user", "content": f"Extract all fields from this NFe XML:\n\n{state['xml_content']}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=4000
            )
            
            extraction_result = json.loads(response.choices[0].message.content)
            
            state['extracted_data'] = extraction_result
            state['confidence_score'] = extraction_result.get('overall_confidence', 0.0)
            state['current_step'] = 'extraction_complete'
            state['processing_notes'].append(f"{self.name}: Field extraction completed")
            
            logger.info(f"{self.name}: Extraction completed with confidence: {state['confidence_score']}")
            
        except Exception as e:
            error_msg = f"{self.name}: Extraction failed - {str(e)}"
            logger.error(error_msg)
            state['errors'].append(error_msg)
            state['current_step'] = 'extraction_failed'
        
        return state

class NFEValidationAgent:
    """Agent responsible for validating extracted NFe data."""
    
    def __init__(self):
        self.name = "NFE_Validation_Agent"
    
    def validate(self, state: AgentState) -> AgentState:
        """Validate the extracted NFe data for consistency and completeness."""
        logger.info(f"{self.name}: Starting data validation")
        
        try:
            validation_prompt = """
            You are an expert in Brazilian NFe validation and compliance.
            Validate the extracted NFe data for:

            1. Required field completeness
            2. Data format compliance (CNPJ, dates, numbers)
            3. Mathematical consistency (totals, calculations)
            4. Tax calculation accuracy
            5. Logical consistency between sections
            6. Compliance with NFe standards

            Identify and fix any issues found.

            Respond with JSON in this format:
            {
                "validation_status": "passed|failed|warning",
                "validated_data": {
                    "corrected_or_confirmed_data_structure"
                },
                "validation_issues": [
                    {
                        "field": "field_name",
                        "issue": "description",
                        "severity": "error|warning|info",
                        "correction": "applied_correction_if_any"
                    }
                ],
                "completeness_score": 0.0-1.0,
                "accuracy_score": 0.0-1.0,
                "final_confidence": 0.0-1.0,
                "validation_notes": ["detailed", "notes"]
            }
            """
            
            extracted_data_str = json.dumps(state['extracted_data'], indent=2, ensure_ascii=False, default=str)
            
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": validation_prompt},
                    {"role": "user", "content": f"Validate this extracted NFe data:\n\n{extracted_data_str}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=4000
            )
            
            validation_result = json.loads(response.choices[0].message.content)
            
            state['validated_data'] = validation_result['validated_data']
            state['confidence_score'] = validation_result.get('final_confidence', state['confidence_score'])
            state['current_step'] = 'validation_complete'
            state['processing_notes'].extend(validation_result.get('validation_notes', []))
            
            # Add validation issues to processing notes
            for issue in validation_result.get('validation_issues', []):
                note = f"Validation {issue['severity']}: {issue['field']} - {issue['issue']}"
                if issue.get('correction'):
                    note += f" (Corrected: {issue['correction']})"
                state['processing_notes'].append(note)
            
            logger.info(f"{self.name}: Validation completed with status: {validation_result['validation_status']}")
            
        except Exception as e:
            error_msg = f"{self.name}: Validation failed - {str(e)}"
            logger.error(error_msg)
            state['errors'].append(error_msg)
            state['current_step'] = 'validation_failed'
        
        return state

class NFEProcessingWorkflow:
    """LangGraph workflow orchestrating the NFe processing agents."""
    
    def __init__(self):
        self.analysis_agent = NFEAnalysisAgent()
        self.extraction_agent = NFEExtractionAgent()
        self.validation_agent = NFEValidationAgent()
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)
        
        # Add nodes (agents)
        workflow.add_node("analyze", self.analysis_agent.analyze)
        workflow.add_node("extract", self.extraction_agent.extract)
        workflow.add_node("validate", self.validation_agent.validate)
        
        # Define the flow
        workflow.set_entry_point("analyze")
        workflow.add_edge("analyze", "extract")
        workflow.add_edge("extract", "validate")
        workflow.set_finish_point("validate")
        
        return workflow.compile()
    
    def process_nfe_xml(self, xml_content: str, raw_data: Dict[str, Any]) -> ProcessingResult:
        """
        Process an NFe XML through the complete AI workflow.
        
        Args:
            xml_content (str): Raw XML content
            raw_data (Dict): Pre-parsed data from XML processor
            
        Returns:
            ProcessingResult: Complete processing results
        """
        logger.info("Starting NFe AI processing workflow")
        
        # Initialize state
        initial_state = AgentState(
            xml_content=xml_content,
            raw_data=raw_data,
            analyzed_data={},
            extracted_data={},
            validated_data={},
            confidence_score=0.0,
            errors=[],
            processing_notes=[],
            current_step="initialized"
        )
        
        try:
            # Run the workflow
            final_state = self.workflow.invoke(initial_state)
            
            # Determine success
            success = (
                len(final_state['errors']) == 0 and
                final_state['current_step'] == 'validation_complete' and
                final_state['confidence_score'] > 0.5
            )
            
            # Prepare final data by merging raw and validated data
            final_data = {}
            if success and final_state['validated_data']:
                final_data = self._merge_data(raw_data, final_state['validated_data'])
                final_data['ai_confidence_score'] = final_state['confidence_score']
                final_data['ai_processing_notes'] = '\n'.join(final_state['processing_notes'])
            
            result = ProcessingResult(
                success=success,
                data=final_data if success else None,
                confidence_score=final_state['confidence_score'],
                errors=final_state['errors'],
                processing_notes=final_state['processing_notes']
            )
            
            logger.info(f"NFe AI processing completed. Success: {success}, Confidence: {final_state['confidence_score']:.2f}")
            return result
            
        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            logger.error(error_msg)
            return ProcessingResult(
                success=False,
                data=None,
                confidence_score=0.0,
                errors=[error_msg],
                processing_notes=["Workflow failed to execute"]
            )
    
    def _merge_data(self, raw_data: Dict[str, Any], validated_data: Dict[str, Any]) -> Dict[str, Any]:
        """Merge raw extracted data with AI-validated data."""
        # Start with raw data as base
        final_data = raw_data.copy()
        
        # Override with validated data where available
        try:
            # Map AI extracted fields to database fields
            if 'identification' in validated_data:
                id_data = validated_data['identification']
                if 'numero_nf' in id_data:
                    final_data['numero_nf'] = id_data['numero_nf'].get('value')
                if 'serie' in id_data:
                    final_data['serie'] = id_data['serie'].get('value')
                # Add more field mappings as needed
            
            if 'issuer' in validated_data:
                issuer_data = validated_data['issuer']
                if 'cnpj' in issuer_data:
                    final_data['emitente_cnpj'] = issuer_data['cnpj'].get('value')
                if 'nome' in issuer_data:
                    final_data['emitente_nome'] = issuer_data['nome'].get('value')
                # Add more field mappings as needed
            
            # Handle items data
            if 'items' in validated_data and isinstance(validated_data['items'], list):
                validated_items = []
                for item in validated_data['items']:
                    validated_item = {}
                    for field, data in item.items():
                        if isinstance(data, dict) and 'value' in data:
                            validated_item[field] = data['value']
                    validated_items.append(validated_item)
                final_data['items'] = validated_items
            
        except Exception as e:
            logger.warning(f"Error merging validated data: {str(e)}")
        
        return final_data

# Global workflow instance
nfe_workflow = NFEProcessingWorkflow()

def process_nfe_with_ai(xml_content: str, raw_data: Dict[str, Any]) -> ProcessingResult:
    """
    Convenience function to process NFe XML with AI agents.
    
    Args:
        xml_content (str): Raw XML content
        raw_data (Dict): Pre-parsed data from XML processor
        
    Returns:
        ProcessingResult: Complete processing results
    """
    return nfe_workflow.process_nfe_xml(xml_content, raw_data)
