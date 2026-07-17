export interface ModelEndpointSettings {
  endpoint: string
  model: string
  timeout_seconds: number
  max_retries: number
}

export interface MdGenSummarySettings {
  prompt_path: string
}

export interface MdGenImageSettings {
  max_longest_edge_px: number
  token_threshold: number
}

export interface MdGenSettings {
  summary: MdGenSummarySettings
  image: MdGenImageSettings
}

export interface MdMrgScoreSettings {
  prompt_path: string
}

export interface MdMrgSettings {
  score: MdMrgScoreSettings
}

export interface AppSettings {
  app_name: string
  version: string
  source_folder: string
  output_folder: string
  verbose: boolean
  overwrite: boolean
  ocr_model: ModelEndpointSettings
  language_model: ModelEndpointSettings
  md_gen: MdGenSettings
  md_mrg: MdMrgSettings
}

export interface ValidationError {
  loc: (string | number)[]
  msg: string
  type: string
}
