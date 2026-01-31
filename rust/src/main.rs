use base64::Engine;
use maplibre_native::{Image, ImageRenderer, ImageRendererBuilder, RenderingError, Static};
use serde::{Deserialize, Serialize};
use std::io::{self, BufRead, Write};
use std::num::NonZeroU32;

#[derive(Debug, Deserialize)]
#[serde(tag = "cmd")]
enum Command {
    #[serde(rename = "init")]
    Init {
        width: u32,
        height: u32,
        style: String,
    },
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
    png: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

struct Renderer {
    renderer: Option<ImageRenderer<Static>>,
    width: u32,
    height: u32,
}

impl Renderer {
    fn new() -> Self {
        Self {
            renderer: None,
            width: 512,
            height: 512,
        }
    }

    fn init(
        &mut self,
        width: u32,
        height: u32,
        style: &str,
    ) -> Result<(), Box<dyn std::error::Error>> {
        self.width = width;
        self.height = height;

        // Convert to NonZeroU32
        let width_nz = NonZeroU32::new(width).ok_or("Width must be non-zero")?;
        let height_nz = NonZeroU32::new(height).ok_or("Height must be non-zero")?;

        let builder = ImageRendererBuilder::new().with_size(width_nz, height_nz);

        let mut renderer = builder.build_static_renderer();

        // Check if style is URL or file path (JSON strings need to be saved to temp file)
        if style.starts_with("http://")
            || style.starts_with("https://")
            || style.starts_with("file://")
        {
            let url = style.parse().map_err(|_| "Invalid style URL")?;
            renderer.load_style_from_url(&url);
        } else if style.starts_with("{") {
            // JSON string - save to temp file
            let temp_dir = std::env::temp_dir();
            let temp_file = temp_dir.join(format!("mlnative_style_{}.json", std::process::id()));
            std::fs::write(&temp_file, style)?;
            renderer.load_style_from_path(&temp_file)?;
            // Note: temp file will be cleaned up by OS eventually
        } else {
            // Assume it's a file path
            renderer.load_style_from_path(style)?;
        }

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

        // Note: render_static takes (lat, lon, zoom, bearing, pitch)
        renderer.render_static(center[1], center[0], zoom, bearing, pitch)
    }
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
                let resp = Response {
                    status: "error".to_string(),
                    png: None,
                    error: Some(format!("Invalid command: {}", e)),
                };
                println!("{}", serde_json::to_string(&resp).unwrap());
                continue;
            }
        };

        match cmd {
            Command::Init {
                width,
                height,
                style,
            } => match renderer.init(width, height, &style) {
                Ok(_) => {
                    let resp = Response {
                        status: "ok".to_string(),
                        png: None,
                        error: None,
                    };
                    println!("{}", serde_json::to_string(&resp).unwrap());
                }
                Err(e) => {
                    let resp = Response {
                        status: "error".to_string(),
                        png: None,
                        error: Some(format!("Init failed: {:?}", e)),
                    };
                    println!("{}", serde_json::to_string(&resp).unwrap());
                }
            },
            Command::Render {
                center,
                zoom,
                bearing,
                pitch,
            } => match renderer.render(center, zoom, bearing, pitch) {
                Ok(image) => {
                    let img_buffer = image.as_image();
                    let mut png_bytes: Vec<u8> = Vec::new();
                    img_buffer
                        .write_to(
                            &mut std::io::Cursor::new(&mut png_bytes),
                            image::ImageFormat::Png,
                        )
                        .expect("Failed to encode PNG");
                    let png_b64 = base64::engine::general_purpose::STANDARD.encode(&png_bytes);
                    let resp = Response {
                        status: "ok".to_string(),
                        png: Some(png_b64),
                        error: None,
                    };
                    println!("{}", serde_json::to_string(&resp).unwrap());
                }
                Err(e) => {
                    let resp = Response {
                        status: "error".to_string(),
                        png: None,
                        error: Some(format!("Render failed: {:?}", e)),
                    };
                    println!("{}", serde_json::to_string(&resp).unwrap());
                }
            },
            Command::RenderBatch { views } => {
                let mut pngs = Vec::new();
                for view in views {
                    match renderer.render(view.center, view.zoom, view.bearing, view.pitch) {
                        Ok(image) => {
                            let img_buffer = image.as_image();
                            let mut png_bytes: Vec<u8> = Vec::new();
                            img_buffer
                                .write_to(
                                    &mut std::io::Cursor::new(&mut png_bytes),
                                    image::ImageFormat::Png,
                                )
                                .expect("Failed to encode PNG");
                            pngs.push(base64::engine::general_purpose::STANDARD.encode(&png_bytes));
                        }
                        Err(e) => {
                            let resp = Response {
                                status: "error".to_string(),
                                png: None,
                                error: Some(format!("Batch render failed: {:?}", e)),
                            };
                            println!("{}", serde_json::to_string(&resp).unwrap());
                            break;
                        }
                    }
                }
                let resp = Response {
                    status: "ok".to_string(),
                    png: Some(pngs.join(",")),
                    error: None,
                };
                println!("{}", serde_json::to_string(&resp).unwrap());
            }
            Command::Quit => {
                break;
            }
        }

        stdout.flush().unwrap();
    }
}
