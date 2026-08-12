export interface Page<T> {
  readonly items: readonly T[]
  readonly total: number
  readonly limit: number
  readonly offset: number
}


export interface Person {
  readonly id: string
  readonly employee_number: string | null
  readonly legal_name: string
  readonly display_name: string
  readonly former_name: string | null
  readonly gender_code: string | null
  readonly birth_date: string | null
  readonly ethnicity_code: string | null
  readonly nationality_code: string | null
  readonly country_code: string | null
  readonly marital_status_code: string | null
  readonly political_status_code: string | null
  readonly status: string
}


export interface Employment {
  readonly id: string
  readonly person_id: string
  readonly employee_type_code: string
  readonly status: string
  readonly planned_start_date: string
  readonly actual_start_date: string | null
  readonly probation_end_date: string | null
  readonly end_date: string | null
  readonly contract_legal_entity_id: string | null
  readonly payroll_legal_entity_id: string | null
  readonly social_insurance_legal_entity_id: string | null
  readonly tax_legal_entity_id: string | null
  readonly version: number
}


export interface EmploymentAssignment {
  readonly id: string
  readonly employment_id: string
  readonly organization_id: string
  readonly job_id: string | null
  readonly relation_type: "primary" | "concurrent" | "secondment" | "project" | "virtual"
  readonly effective_from: string
  readonly effective_to: string | null
  readonly version: number
}


export interface EmploymentLegalEntityRelation {
  readonly id: string
  readonly employment_id: string
  readonly relation_kind: "contract" | "payroll" | "social_insurance" | "tax"
  readonly legal_entity_id: string
  readonly effective_from: string
  readonly effective_to: string | null
  readonly source_event_id: string | null
  readonly version: number
  readonly change_reason: string
}


export interface AgreementRelationship {
  readonly id: string
  readonly person_id: string
  readonly agreement_type_code: string
  readonly legal_entity_id: string | null
  readonly counterparty_name: string | null
  readonly effective_from: string
  readonly effective_to: string | null
  readonly source: string
}


export interface PersonArchive {
  readonly person: Person
  readonly employments: readonly Employment[]
  readonly legal_entity_relations: readonly EmploymentLegalEntityRelation[]
  readonly assignments: readonly EmploymentAssignment[]
  readonly agreements: readonly AgreementRelationship[]
}


export interface PersonDocument {
  readonly id: string
  readonly document_type_code: string
  readonly masked_document_number: string
  readonly issuing_country_code: string
  readonly issue_date: string | null
  readonly expiry_date: string | null
  readonly is_primary: boolean
  readonly verification_status: string
  readonly effective_from: string
  readonly effective_to: string | null
}


export interface PersonContact {
  readonly id: string
  readonly contact_type: "personal_phone" | "work_phone" | "personal_email" | "work_email"
  readonly masked_contact_value: string
  readonly is_primary: boolean
  readonly effective_from: string
  readonly effective_to: string | null
}


export interface PersonAddress {
  readonly id: string
  readonly address_type: "residential" | "mailing"
  readonly country_code: string
  readonly region_code: string | null
  readonly masked_address_detail: string
  readonly effective_from: string
  readonly effective_to: string | null
}


export interface EmergencyContact {
  readonly id: string
  readonly masked_name: string
  readonly relationship_code: string
  readonly masked_phone: string
  readonly effective_from: string
  readonly effective_to: string | null
}


export interface EducationRecord {
  readonly id: string
  readonly masked_institution_name: string
  readonly education_level_code: string
  readonly masked_major_name: string | null
  readonly study_start_date: string
  readonly study_end_date: string | null
}


export interface WorkExperience {
  readonly id: string
  readonly masked_employer_name: string
  readonly masked_job_title: string | null
  readonly work_start_date: string
  readonly work_end_date: string | null
}


export interface FamilyMember {
  readonly id: string
  readonly masked_name: string
  readonly relationship_code: string
  readonly effective_from: string
  readonly effective_to: string | null
}


export interface PersonnelSubrecords {
  readonly documents: readonly PersonDocument[]
  readonly contacts: readonly PersonContact[]
  readonly addresses: readonly PersonAddress[]
  readonly emergencyContacts: readonly EmergencyContact[]
  readonly educationRecords: readonly EducationRecord[]
  readonly workExperiences: readonly WorkExperience[]
  readonly familyMembers: readonly FamilyMember[]
}


export interface Job {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly level_code: string
  readonly grade_code: string
  readonly class_code: string
  readonly sequence_code: string
  readonly status: string
  readonly effective_from: string
  readonly effective_to: string | null
  readonly version: number
  readonly source_job_id: string | null
  readonly notes: string | null
  readonly attributes: Readonly<Record<string, unknown>>
}


export interface JobDimension {
  readonly id: string
  readonly dimension_type: "LEVEL" | "GRADE" | "CLASS" | "SEQUENCE"
  readonly code: string
  readonly name: string
  readonly parent_dimension_id: string | null
  readonly parent_dimension_type: "LEVEL" | "GRADE" | "CLASS" | "SEQUENCE" | null
  readonly parent_dimension_code: string | null
  readonly sort_order: number
  readonly status: string
  readonly effective_from: string
  readonly effective_to: string | null
  readonly version: number
  readonly notes: string | null
}


export interface LegalEntity {
  readonly id: string
  readonly code: string
  readonly name: string
  readonly country_code: string
  readonly status: string
  readonly effective_from: string
  readonly effective_to: string | null
}


export interface OrganizationOption {
  readonly id: string
  readonly code: string
  readonly name: string
}


export interface OccupancyRule {
  readonly id: string
  readonly employee_type_code: string
  readonly counts_for_headcount: boolean
  readonly effective_from: string
  readonly effective_to: string | null
  readonly version: number
}


export interface HeadcountFreeze {
  readonly id: string
  readonly freeze_type: "month_close" | "business"
  readonly period_month: string | null
  readonly organization_id: string | null
  readonly job_id: string | null
  readonly status: string
  readonly starts_at: string
  readonly ends_at: string | null
  readonly reason: string
}


export interface HeadcountResultLine {
  readonly organization_id: string
  readonly organization_code: string
  readonly job_id: string
  readonly job_code: string
  readonly job_name: string
  readonly period_month: string
  readonly planned_count: string
  readonly plan_version: number
  readonly current_count: number
  readonly variance: string
  readonly month_start_count: number | null
  readonly month_end_count: number | null
  readonly average_count: string | null
  readonly frozen: boolean
}


export interface HeadcountResult {
  readonly period_month: string
  readonly as_of: string
  readonly items: readonly HeadcountResultLine[]
}


export interface RecruitmentRequest {
  readonly id: string
  readonly request_number: string
  readonly organization_id: string
  readonly job_id: string
  readonly requested_count: number
  readonly target_month: string | null
  readonly status: "draft" | "submitted" | "closed" | "cancelled"
  readonly reason: string
  readonly workflow_instance_id: string | null
}
