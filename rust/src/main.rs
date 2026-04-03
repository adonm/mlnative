use maplibre_native::{Image, ImageRenderer, ImageRendererBuilder, RenderingError, Static};
use serde::{Deserialize, Serialize};
use std::io::{self, BufRead, Write};
use std::num::NonZeroU32;
use tempfile::NamedTempFile;

const PROTOCOL_VERSION: &str = "2.0";

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
}

#[derive(Debug, Serialize)]
struct Response {
    status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    png_len: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    png_lengths: Option<Vec<usize>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

struct Renderer {
    renderer: Option<ImageRenderer<Static>>,
    temp_style_file: Option<NamedTempFile>,
}

impl Renderer {
    fn new() -> Self {
        Self {
            renderer: None,
            temp_style_file: None,
        }
    }

    fn load_style(
        renderer: &mut ImageRenderer<Static>,
        style: &str,
        temp_style_file: &mut Option<NamedTempFile>,
    ) -> Result<(), Box<dyn std::error::Error>> {
        if style.starts_with("http://")
            || style.starts_with("https://")
            || style.starts_with("file://")
        {
            let url = style.parse().map_err(|_| "Invalid style URL")?;
            renderer.load_style_from_url(&url);
            Ok(())
        } else if style.starts_with("{") {
            if temp_style_file.is_none() {
                *temp_style_file = Some(NamedTempFile::new()?);
            }
            let temp_file = temp_style_file
                .as_mut()
                .ok_or("temporary style file unavailable")?;
            temp_file.as_file_mut().set_len(0)?;
            temp_file.as_file_mut().write_all(style.as_bytes())?;
            temp_file.as_file_mut().flush()?;
            renderer.load_style_from_path(temp_file.path())?;
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
        let width_nz = NonZeroU32::new(width).ok_or("Width must be non-zero")?;
        let height_nz = NonZeroU32::new(height).ok_or("Height must be non-zero")?;

        let builder = ImageRendererBuilder::new()
            .with_size(width_nz, height_nz)
            .with_pixel_ratio(pixel_ratio as f32);

        let mut renderer = builder.build_static_renderer();
        Self::load_style(&mut renderer, style, &mut self.temp_style_file)?;

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

    fn reload_style(&mut self, style: &str) -> Result<(), Box<dyn std::error::Error>> {
        let renderer = self
            .renderer
            .as_mut()
            .ok_or("Renderer not initialized")?;

        Self::load_style(renderer, style, &mut self.temp_style_file)
    }
}

fn encode_png(image: Image) -> Result<Vec<u8>, String> {
    let img_buffer = image.as_image();
    let mut png_bytes: Vec<u8> = Vec::new();
    img_buffer
        .write_to(
            &mut std::io::Cursor::new(&mut png_bytes),
            image::ImageFormat::Png,
        )
        .map_err(|e| format!("Failed to encode PNG: {}", e))?;
    Ok(png_bytes)
}

fn send_response(resp: &Response) {
    println!(
        "{}",
        serde_json::to_string(resp).unwrap_or_else(|_| {
            r#"{"status":"error","error":"JSON encode failed"}"#.to_string()
        })
    );
    let _ = io::stdout().flush();
}

fn send_response_with_payload(resp: &Response, payload: &[u8]) {
    send_response(resp);
    let _ = io::stdout().write_all(payload);
    let _ = io::stdout().flush();
}

fn send_response_with_chunks<'a>(resp: &Response, chunks: impl IntoIterator<Item = &'a [u8]>) {
    send_response(resp);
    let mut stdout = io::stdout();
    for chunk in chunks {
        let _ = stdout.write_all(chunk);
    }
    let _ = stdout.flush();
}

fn main() {
    let stdin = io::stdin();
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
                    png_len: None,
                    png_lengths: None,
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
                            png_len: None,
                            png_lengths: None,
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
                        png_len: None,
                        png_lengths: None,
                        error: None,
                    }),
                    Err(_) => send_response(&Response {
                        status: "error".to_string(),
                        png_len: None,
                        png_lengths: None,
                        error: Some("Init failed".to_string()),
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
                    Ok(png_bytes) => send_response_with_payload(
                        &Response {
                            status: "ok".to_string(),
                            png_len: Some(png_bytes.len()),
                            png_lengths: None,
                            error: None,
                        },
                        &png_bytes,
                    ),
                    Err(e) => send_response(&Response {
                        status: "error".to_string(),
                        png_len: None,
                        png_lengths: None,
                        error: Some(e),
                    }),
                },
                Err(e) => send_response(&Response {
                    status: "error".to_string(),
                    png_len: None,
                    png_lengths: None,
                    error: Some("Render failed".to_string()),
                }),
            },
            Command::ReloadStyle { style } => match renderer.reload_style(&style) {
                Ok(_) => send_response(&Response {
                    status: "ok".to_string(),
                    png_len: None,
                    png_lengths: None,
                    error: None,
                }),
                Err(_) => send_response(&Response {
                    status: "error".to_string(),
                    png_len: None,
                    png_lengths: None,
                    error: Some("Reload style failed".to_string()),
                }),
            },
            Command::RenderBatch { views } => {
                let mut png_batches = Vec::with_capacity(views.len());
                let mut png_lengths = Vec::with_capacity(views.len());
                let mut error_response: Option<Response> = None;

                for view in views {
                    match renderer.render(view.center, view.zoom, view.bearing, view.pitch) {
                        Ok(image) => match encode_png(image) {
                            Ok(png_bytes) => {
                                png_lengths.push(png_bytes.len());
                                png_batches.push(png_bytes);
                            }
                            Err(_) => {
                                error_response = Some(Response {
                                    status: "error".to_string(),
                                    png_len: None,
                                    png_lengths: None,
                                    error: Some("PNG encoding failed".to_string()),
                                });
                                break;
                            }
                        },
                        Err(_) => {
                            error_response = Some(Response {
                                status: "error".to_string(),
                                png_len: None,
                                png_lengths: None,
                                error: Some("Batch render failed".to_string()),
                            });
                            break;
                        }
                    }
                }

                if let Some(resp) = error_response {
                    send_response(&resp);
                } else {
                    send_response_with_chunks(
                        &Response {
                            status: "ok".to_string(),
                            png_len: None,
                            png_lengths: Some(png_lengths),
                            error: None,
                        },
                        png_batches.iter().map(Vec::as_slice),
                    );
                }
            }
            Command::Quit => break,
        }
    }
}
