export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      alerts: {
        Row: {
          alert_type: string
          change_id: string | null
          channel: string
          delivered: boolean
          error_message: string | null
          fingerprint: string
          id: string
          message_content: string
          monitor_id: string
          offer_id: string | null
          sent_at: string
          user_id: string
        }
        Insert: {
          alert_type: string
          change_id?: string | null
          channel?: string
          delivered?: boolean
          error_message?: string | null
          fingerprint: string
          id?: string
          message_content: string
          monitor_id: string
          offer_id?: string | null
          sent_at?: string
          user_id: string
        }
        Update: {
          alert_type?: string
          change_id?: string | null
          channel?: string
          delivered?: boolean
          error_message?: string | null
          fingerprint?: string
          id?: string
          message_content?: string
          monitor_id?: string
          offer_id?: string | null
          sent_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "alerts_change_id_fkey"
            columns: ["change_id"]
            isOneToOne: false
            referencedRelation: "offer_changes"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "alerts_monitor_id_fkey"
            columns: ["monitor_id"]
            isOneToOne: false
            referencedRelation: "monitors"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "alerts_offer_id_fkey"
            columns: ["offer_id"]
            isOneToOne: false
            referencedRelation: "offers"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "alerts_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      courses: {
        Row: {
          active: boolean
          category: string | null
          created_at: string
          external_id: string | null
          id: string
          institution_id: string
          name: string
          slug: string
        }
        Insert: {
          active?: boolean
          category?: string | null
          created_at?: string
          external_id?: string | null
          id?: string
          institution_id: string
          name: string
          slug: string
        }
        Update: {
          active?: boolean
          category?: string | null
          created_at?: string
          external_id?: string | null
          id?: string
          institution_id?: string
          name?: string
          slug?: string
        }
        Relationships: [
          {
            foreignKeyName: "courses_institution_id_fkey"
            columns: ["institution_id"]
            isOneToOne: false
            referencedRelation: "institutions"
            referencedColumns: ["id"]
          },
        ]
      }
      institutions: {
        Row: {
          active: boolean
          created_at: string
          id: string
          name: string
          slug: string
          state: string
        }
        Insert: {
          active?: boolean
          created_at?: string
          id?: string
          name: string
          slug: string
          state?: string
        }
        Update: {
          active?: boolean
          created_at?: string
          id?: string
          name?: string
          slug?: string
          state?: string
        }
        Relationships: []
      }
      locations: {
        Row: {
          active: boolean
          city: string
          created_at: string
          external_id: string | null
          id: string
          institution_id: string
          name: string
          slug: string
          state: string
        }
        Insert: {
          active?: boolean
          city: string
          created_at?: string
          external_id?: string | null
          id?: string
          institution_id: string
          name: string
          slug: string
          state?: string
        }
        Update: {
          active?: boolean
          city?: string
          created_at?: string
          external_id?: string | null
          id?: string
          institution_id?: string
          name?: string
          slug?: string
          state?: string
        }
        Relationships: [
          {
            foreignKeyName: "locations_institution_id_fkey"
            columns: ["institution_id"]
            isOneToOne: false
            referencedRelation: "institutions"
            referencedColumns: ["id"]
          },
        ]
      }
      monitor_preferences: {
        Row: {
          created_at: string
          id: string
          monitor_id: string
          notify_date_changes: boolean
          notify_enrollment_open: boolean
          notify_new_class: boolean
          notify_new_offer: boolean
          notify_paid: boolean
          notify_scholarship: boolean
        }
        Insert: {
          created_at?: string
          id?: string
          monitor_id: string
          notify_date_changes?: boolean
          notify_enrollment_open?: boolean
          notify_new_class?: boolean
          notify_new_offer?: boolean
          notify_paid?: boolean
          notify_scholarship?: boolean
        }
        Update: {
          created_at?: string
          id?: string
          monitor_id?: string
          notify_date_changes?: boolean
          notify_enrollment_open?: boolean
          notify_new_class?: boolean
          notify_new_offer?: boolean
          notify_paid?: boolean
          notify_scholarship?: boolean
        }
        Relationships: [
          {
            foreignKeyName: "monitor_preferences_monitor_id_fkey"
            columns: ["monitor_id"]
            isOneToOne: true
            referencedRelation: "monitors"
            referencedColumns: ["id"]
          },
        ]
      }
      monitors: {
        Row: {
          active: boolean
          course_id: string
          created_at: string
          id: string
          institution_id: string
          location_id: string
          shift: string | null
          updated_at: string
          user_id: string
        }
        Insert: {
          active?: boolean
          course_id: string
          created_at?: string
          id?: string
          institution_id: string
          location_id: string
          shift?: string | null
          updated_at?: string
          user_id: string
        }
        Update: {
          active?: boolean
          course_id?: string
          created_at?: string
          id?: string
          institution_id?: string
          location_id?: string
          shift?: string | null
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "monitors_course_id_fkey"
            columns: ["course_id"]
            isOneToOne: false
            referencedRelation: "courses"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "monitors_institution_id_fkey"
            columns: ["institution_id"]
            isOneToOne: false
            referencedRelation: "institutions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "monitors_location_id_fkey"
            columns: ["location_id"]
            isOneToOne: false
            referencedRelation: "locations"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "monitors_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      offer_changes: {
        Row: {
          change_type: string
          current_state_json: Json | null
          detected_at: string
          id: string
          is_actionable: boolean
          offer_id: string
          previous_state_json: Json | null
          reasons: string[] | null
        }
        Insert: {
          change_type: string
          current_state_json?: Json | null
          detected_at?: string
          id?: string
          is_actionable?: boolean
          offer_id: string
          previous_state_json?: Json | null
          reasons?: string[] | null
        }
        Update: {
          change_type?: string
          current_state_json?: Json | null
          detected_at?: string
          id?: string
          is_actionable?: boolean
          offer_id?: string
          previous_state_json?: Json | null
          reasons?: string[] | null
        }
        Relationships: [
          {
            foreignKeyName: "offer_changes_offer_id_fkey"
            columns: ["offer_id"]
            isOneToOne: false
            referencedRelation: "offers"
            referencedColumns: ["id"]
          },
        ]
      }
      offer_checks: {
        Row: {
          checked_at: string
          diff_json: Json | null
          error_message: string | null
          id: string
          is_success: boolean
          offer_id: string
          state_json: Json | null
          status_code: number
        }
        Insert: {
          checked_at?: string
          diff_json?: Json | null
          error_message?: string | null
          id?: string
          is_success: boolean
          offer_id: string
          state_json?: Json | null
          status_code?: number
        }
        Update: {
          checked_at?: string
          diff_json?: Json | null
          error_message?: string | null
          id?: string
          is_success?: boolean
          offer_id?: string
          state_json?: Json | null
          status_code?: number
        }
        Relationships: [
          {
            foreignKeyName: "offer_checks_offer_id_fkey"
            columns: ["offer_id"]
            isOneToOne: false
            referencedRelation: "offers"
            referencedColumns: ["id"]
          },
        ]
      }
      offers: {
        Row: {
          active: boolean
          bolsa_disponivel: boolean
          course_id: string
          current_state_hash: string | null
          current_state_json: Json | null
          external_offer_id: string
          first_detected_at: string
          id: string
          inscricao_disponivel: boolean
          institution_id: string
          last_changed_at: string
          last_checked_at: string
          location_id: string
          shift: string
          status: string
          url: string
        }
        Insert: {
          active?: boolean
          bolsa_disponivel?: boolean
          course_id: string
          current_state_hash?: string | null
          current_state_json?: Json | null
          external_offer_id: string
          first_detected_at?: string
          id?: string
          inscricao_disponivel?: boolean
          institution_id: string
          last_changed_at?: string
          last_checked_at?: string
          location_id: string
          shift: string
          status?: string
          url: string
        }
        Update: {
          active?: boolean
          bolsa_disponivel?: boolean
          course_id?: string
          current_state_hash?: string | null
          current_state_json?: Json | null
          external_offer_id?: string
          first_detected_at?: string
          id?: string
          inscricao_disponivel?: boolean
          institution_id?: string
          last_changed_at?: string
          last_checked_at?: string
          location_id?: string
          shift?: string
          status?: string
          url?: string
        }
        Relationships: [
          {
            foreignKeyName: "offers_course_id_fkey"
            columns: ["course_id"]
            isOneToOne: false
            referencedRelation: "courses"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "offers_institution_id_fkey"
            columns: ["institution_id"]
            isOneToOne: false
            referencedRelation: "institutions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "offers_location_id_fkey"
            columns: ["location_id"]
            isOneToOne: false
            referencedRelation: "locations"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          created_at: string
          email: string
          id: string
          name: string | null
          role: string
          status: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          email: string
          id: string
          name?: string | null
          role?: string
          status?: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          email?: string
          id?: string
          name?: string | null
          role?: string
          status?: string
          updated_at?: string
        }
        Relationships: []
      }
      system_errors: {
        Row: {
          created_at: string
          error_type: string
          id: string
          message: string
          source: string
          stack_trace: string | null
        }
        Insert: {
          created_at?: string
          error_type: string
          id?: string
          message: string
          source: string
          stack_trace?: string | null
        }
        Update: {
          created_at?: string
          error_type?: string
          id?: string
          message?: string
          source?: string
          stack_trace?: string | null
        }
        Relationships: []
      }
      telegram_accounts: {
        Row: {
          active: boolean
          created_at: string
          id: string
          telegram_chat_id: string
          telegram_first_name: string | null
          telegram_username: string | null
          updated_at: string
          user_id: string
          verified_at: string
        }
        Insert: {
          active?: boolean
          created_at?: string
          id?: string
          telegram_chat_id: string
          telegram_first_name?: string | null
          telegram_username?: string | null
          updated_at?: string
          user_id: string
          verified_at?: string
        }
        Update: {
          active?: boolean
          created_at?: string
          id?: string
          telegram_chat_id?: string
          telegram_first_name?: string | null
          telegram_username?: string | null
          updated_at?: string
          user_id?: string
          verified_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "telegram_accounts_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: true
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      telegram_link_tokens: {
        Row: {
          created_at: string
          expires_at: string
          id: string
          token: string
          used_at: string | null
          user_id: string
        }
        Insert: {
          created_at?: string
          expires_at: string
          id?: string
          token: string
          used_at?: string | null
          user_id: string
        }
        Update: {
          created_at?: string
          expires_at?: string
          id?: string
          token?: string
          used_at?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "telegram_link_tokens_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      worker_health: {
        Row: {
          cycle_duration_seconds: number | null
          heartbeat_at: string
          id: string
          last_cycle_at: string | null
          metadata: Json | null
          offers_checked: number | null
          offers_failed: number | null
          offers_succeeded: number | null
          status: string
          worker_id: string
        }
        Insert: {
          cycle_duration_seconds?: number | null
          heartbeat_at?: string
          id?: string
          last_cycle_at?: string | null
          metadata?: Json | null
          offers_checked?: number | null
          offers_failed?: number | null
          offers_succeeded?: number | null
          status?: string
          worker_id: string
        }
        Update: {
          cycle_duration_seconds?: number | null
          heartbeat_at?: string
          id?: string
          last_cycle_at?: string | null
          metadata?: Json | null
          offers_checked?: number | null
          offers_failed?: number | null
          offers_succeeded?: number | null
          status?: string
          worker_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      is_admin: { Args: never; Returns: boolean }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}
