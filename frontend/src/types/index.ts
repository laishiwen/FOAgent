export interface SourceSchema {
  [fileId: string]: {
    name: string;
    path: string;
    extension?: string;
    size_bytes?: number;
    modified_at?: string;
    parent_id: string;
    is_dir: boolean;
  };
}

export interface DirEntry {
  id: string;
  name: string;
  path: string;
  parent_id: string | null;
}

export interface CategoryGroup {
  category_name: string;
  member_ids: string[];
  member_names: string[];
  count: number;
}

export interface ProgressEvent {
  phase: "scanning" | "classifying" | "merging" | "done";
  current: number;
  total: number;
  message: string;
}

export interface ClassifyResult {
  success: boolean;
  root_path: string;
  stats: {
    file_count: number;
    dir_count: number;
    by_extension: Record<string, number>;
  };
  dir_tree: DirEntry[];
  source_schema: SourceSchema;
  categories: CategoryGroup[];
  category_order: string[];
  total_files: number;
  error?: string;
}
