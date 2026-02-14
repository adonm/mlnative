use base64::Engine;
use maplibre_native::{Image, ImageRenderer, ImageRendererBuilder, RenderingError, Static};
use serde::{Deserialize, Serialize};
use std::io::{self, BufRead, Write};
use std::num::NonZeroU32;

const PROTOCOL_VERSION: &str = "1.0";

fn default_pixel_ratio() -> f64 {
    1.0
}

#[derive(Debug, Deserialize)]
#[serde(tag = "cmd")]
enum Command {
    #[serde(rename = "init")]
    Init {
        width: u32,
        height: u32,
        style: String,
        #[serde(default = "default_pixel_ratio")]
        pixel_ratio: f64,
        #[serde(default)]
        protocol_version: Option<String>,
    },
    #[serde(rename = "reload_style")]
    ReloadStyle { style: String },
    #[serde(rename = "render")]
    Render {
        center: [f64; 2],
        zoom: f64,
        #[serde(default)]
        bearing: f64,
        #[serde(default)]
        pitch: f64,
    },
    #[serde(rename = "render_batch")]
    RenderBatch { views: Vec<View> },
    #[serde(rename = "quit")]
    Quit,
}

#[derive(Debug, Deserialize)]
struct View {
    center: [f64; 2],
    zoom: f64,
    #[serde(default)]
    bearing: f64,
    #[serde(default)]
    pitch: f64,
    #[serde(default)]
    geojson: Option<std::collections::HashMap<String, serde_json::Value>>,
}

#[derive(Debug, Serialize)]
struct Response {
    status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    png: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

struct Renderer {
    renderer: Option<ImageRenderer<Static>>,
    width: u32,
    height: u32,
    temp_files: Vec<std::path::PathBuf>,
}

impl Renderer {
    fn new() -> Self {
        Self {
            renderer: None,
            width: 512,
            height: 512,
            temp_files: Vec::new(),
        }
    }

    fn cleanup_temp_files(&mut self) {
        for path in &self.temp_files {
            let _ = std::fs::remove_file(path);
        }
        self.temp_files.clear();
    }

    fn load_style(
        renderer: &mut ImageRenderer<Static>,
        style: &str,
        temp_files: &mut Vec<std::path::PathBuf>,
    ) -> Result<(), Box<dyn std::error::Error>> {
        if style.starts_with("http://")
            || style.starts_with("https://")
            || style.starts_with("file://")
        {
            let url = style.parse().map_err(|_| "Invalid style URL")?;
            renderer.load_style_from_url(&url);
            Ok(())
        } else if style.starts_with("{") {
            let temp_dir = std::env::temp_dir();
            let temp_file = temp_dir.join(format!(
                "mlnative_style_{}_{}.json",
                std::process::id(),
                temp_files.len()
            ));
            std::fs::write(&temp_file, style)?;
            renderer.load_style_from_path(&temp_file)?;
            temp_files.push(temp_file);
            Ok(())
        } else {
            renderer.load_style_from_path(style)?;
            Ok(())
        }
    }

    fn init(
        &mut self,
        width: u32,
        height: u32,
        style: &str,
        pixel_ratio: f64,
    ) -> Result<(), Box<dyn std::error::Error>> {
        self.width = width;
        self.height = height;

        let width_nz = NonZeroU32::new(width).ok_or("Width must be non-zero")?;
        let height_nz = NonZeroU32::new(height).ok_or("Height must be non-zero")?;

        let builder = ImageRendererBuilder::new()
            .with_size(width_nz, height_nz)
            .with_pixel_ratio(pixel_ratio as f32);

        let mut renderer = builder.build_static_renderer();
        Self::load_style(&mut renderer, style, &mut self.temp_files)?;

        self.renderer = Some(renderer);
        Ok(())
    }

    fn render(
        &mut self,
        center: [f64; 2],
        zoom: f64,
        bearing: f64,
        pitch: f64,
    ) -> Result<Image, RenderingError> {
        let renderer = self
            .renderer
            .as_mut()
            .ok_or(RenderingError::StyleNotSpecified)?;

        let image = renderer.render_static(center[1], center[0], zoom, bearing, pitch)?;

        Ok(image)
    }

    fn update_geojson_sources(
        &mut self,
        _geojson_updates: &std::collections::HashMap<String, serde_json::Value>,
    ) -> Result<(), Box<dyn std::error::Error>> {
        Ok(())
    }

    fn reload_style(&mut self, style: &str) -> Result<(), Box<dyn std::error::Error>> {
        let renderer = self
            .renderer
            .as_mut()
            .ok_or("Renderer not initialized")?;

        Self::load_style(renderer, style, &mut self.temp_files)
    }
}

fn encode_png(image: Image) -> Result<String, String> {
    let img_buffer = image.as_image();
    let mut png_bytes: Vec<u8> = Vec::new();
    img_buffer
        .write_to(
            &mut std::io::Cursor::new(&mut png_bytes),
            image::ImageFormat::Png,
        )
        .map_err(|e| format!("Failed to encode PNG: {}", e))?;
    Ok(base64::engine::general_purpose::STANDARD.encode(&png_bytes))
}

fn send_response(resp: &Response) {
    println!(
        "{}",
        serde_json::to_string(resp).unwrap_or_else(|_| r#"{"status":"error","error":"JSON encode failed"}"#.to_string())
    );
}

fn main() {
    let stdin = io::stdin();
    let mut stdout = io::stdout();
    let mut renderer = Renderer::new();

    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };

        if line.trim().is_empty() {
            continue;
        }

        let cmd: Command = match serde_json::from_str(&line) {
            Ok(c) => c,
            Err(e) => {
                send_response(&Response {
                    status: "error".to_string(),
                    png: None,
                    error: Some(format!("Invalid command: {}", e)),
                });
                continue;
            }
        };

        match cmd {
            Command::Init {
                width,
                height,
                style,
                pixel_ratio,
                protocol_version,
            } => {
                if let Some(ref version) = protocol_version {
                    if version != PROTOCOL_VERSION {
                        send_response(&Response {
                            status: "error".to_string(),
                            png: None,
                            error: Some(format!(
                                "Protocol version mismatch: client={}, daemon={}",
                                version, PROTOCOL_VERSION
                            )),
                        });
                        continue;
                    }
                }
                match renderer.init(width, height, &style, pixel_ratio) {
                    Ok(_) => send_response(&Response {
                        status: "ok".to_string(),
                        png: None,
                        error: None,
                    }),
                    Err(e) => send_response(&Response {
                        status: "error".to_string(),
                        png: None,
                        error: Some(format!("Init failed: {:?}", e)),
                    }),
                }
            }
            Command::Render {
                center,
                zoom,
                bearing,
                pitch,
            } => match renderer.render(center, zoom, bearing, pitch) {
                Ok(image) => match encode_png(image) {
                    Ok(png_b64) => send_response(&Response {
                        status: "ok".to_string(),
                        png: Some(png_b64),
                        error: None,
                    }),
                    Err(e) => send_response(&Response {
                        status: "error".to_string(),
                        png: None,
                        error: Some(e),
                    }),
                },
                Err(e) => send_response(&Response {
                    status: "error".to_string(),
                    png: None,
                    error: Some(format!("Render failed: {:?}", e)),
                }),
            },
            Command::ReloadStyle { style } => match renderer.reload_style(&style) {
                Ok(_) => send_response(&Response {
                    status: "ok".to_string(),
                    png: None,
                    error: None,
                }),
                Err(e) => send_response(&Response {
                    status: "error".to_string(),
                    png: None,
                    error: Some(format!("Reload style failed: {:?}", e)),
                }),
            },
            Command::RenderBatch { views } => {
                let mut pngs = Vec::new();
                let mut error_response: Option<Response> = None;

                for view in views {
                    if let Some(geojson) = &view.geojson {
                        if let Err(e) = renderer.update_geojson_sources(geojson) {
                            error_response = Some(Response {
                                status: "error".to_string(),
                                png: None,
                                error: Some(format!("GeoJSON update failed: {:?}", e)),
                            });
                            break;
                        }
                    }

                    match renderer.render(view.center, view.zoom, view.bearing, view.pitch) {
                        Ok(image) => match encode_png(image) {
                            Ok(png_b64) => pngs.push(png_b64),
                            Err(e) => {
                                error_response = Some(Response {
                                    status: "error".to_string(),
                                    png: None,
                                    error: Some(e),
                                });
                                break;
                            }
                        },
                        Err(e) => {
                            error_response = Some(Response {
                                status: "error".to_string(),
                                png: None,
                                error: Some(format!("Batch render failed: {:?}", e)),
                            });
                            break;
                        }
                    }
                }

                if let Some(resp) = error_response {
                    send_response(&resp);
                } else {
                    send_response(&Response {
                        status: "ok".to_string(),
                        png: Some(pngs.join(",")),
                        error: None,
                    });
                }
            }
            Command::Quit => {
                renderer.cleanup_temp_files();
                break;
            }
        }

        let _ = stdout.flush();
    }
}
