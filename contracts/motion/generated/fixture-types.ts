// Generated compile-time fixture check. No rendering or assets.
import type {MotionComposition} from "./motion-contracts";
export const sports = {
  "schema_version": "motion_composition_v1",
  "project_id": "fixture-sports",
  "expected": {
    "storyboard_revision": 1,
    "snapshot_sha256": "9da07fdd67ba713763d7c90f27b99469a821b746687ee97cda9bbf56bc6e6531",
    "canvas": {
      "width": 1080,
      "height": 1920,
      "fps_num": 30,
      "fps_den": 1
    },
    "duration_ms": 12000
  },
  "recipe": {
    "id": "sports.depth-impact",
    "version": "1.0.0",
    "sha256": "9b4a5dd40111743d9561e2b92bfb77ecee777c61444fed1f035a64cfc381b061"
  },
  "asset_bindings": {
    "score": {
      "asset_id": "fixture-sports-score",
      "sha256": "27f66550e5b6ee39a17db8ddef59fc98f329c141a50a4486674df120d0f38066",
      "byte_size": 1024,
      "kind": "audio",
      "duration_ms": 12000,
      "sample_rate": 48000,
      "channels": 2
    }
  },
  "scenes": [
    {
      "shot_id": "main",
      "graph": {
        "schema_version": "motion_scene_v1",
        "safe_area": {
          "left": 72,
          "right": 72,
          "top": 120,
          "bottom": 180
        },
        "camera": {
          "position": [
            0.0,
            0.0,
            0.0
          ],
          "rotate_z": 0.0,
          "focal_length": 1200.0,
          "animations": [
            {
              "property": "position",
              "keyframes": [
                {
                  "time": {
                    "kind": "ms",
                    "at_ms": 0
                  },
                  "easing": "cubic_in_out",
                  "value": [
                    0.0,
                    0.0,
                    0.0
                  ]
                },
                {
                  "time": {
                    "kind": "ms",
                    "at_ms": 4800
                  },
                  "easing": "cubic_in_out",
                  "value": [
                    60.0,
                    -30.0,
                    120.0
                  ]
                },
                {
                  "time": {
                    "kind": "ms",
                    "at_ms": 10000
                  },
                  "easing": "cubic_in_out",
                  "value": [
                    0.0,
                    0.0,
                    40.0
                  ]
                }
              ]
            }
          ]
        },
        "nodes": [
          {
            "position": [
              110.0,
              600.0,
              600.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 0.18,
            "animations": [
              {
                "property": "position",
                "keyframes": [
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 0
                    },
                    "easing": "cubic_in_out",
                    "value": [
                      110.0,
                      600.0,
                      600.0
                    ]
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 10000
                    },
                    "easing": "cubic_in_out",
                    "value": [
                      -80.0,
                      500.0,
                      600.0
                    ]
                  }
                ]
              }
            ],
            "id": "back-title",
            "parent_id": null,
            "space": "world",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "text",
            "params": {
              "text": {
                "kind": "shot_field",
                "field": "on_screen_text"
              },
              "font": {
                "kind": "dna_font",
                "index": 0
              },
              "fill": {
                "kind": "dna_palette",
                "index": 1
              },
              "size": 260.0,
              "max_width": 936.0,
              "line_height": 1.0,
              "max_lines": 6,
              "align": "left",
              "method": "fade_slide"
            }
          },
          {
            "position": [
              90.0,
              660.0,
              0.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [
              {
                "property": "scale",
                "keyframes": [
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 0
                    },
                    "easing": "cubic_in_out",
                    "value": [
                      0.92,
                      0.92
                    ]
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 300
                    },
                    "easing": "cubic_out",
                    "value": [
                      1.0,
                      1.0
                    ]
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 10500
                    },
                    "easing": "cubic_in_out",
                    "value": [
                      1.02,
                      1.02
                    ]
                  }
                ]
              }
            ],
            "id": "hero",
            "parent_id": null,
            "space": "screen",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "group"
          },
          {
            "position": [
              0.0,
              0.0,
              0.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [],
            "id": "title",
            "parent_id": "hero",
            "space": "screen",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "text",
            "params": {
              "text": {
                "kind": "shot_field",
                "field": "on_screen_text"
              },
              "font": {
                "kind": "dna_font",
                "index": 0
              },
              "fill": {
                "kind": "dna_palette",
                "index": 1
              },
              "size": 210.0,
              "max_width": 900.0,
              "line_height": 1.0,
              "max_lines": 6,
              "align": "left",
              "method": "fade_slide"
            }
          },
          {
            "position": [
              0.0,
              0.0,
              0.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [
              {
                "property": "opacity",
                "keyframes": [
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 0
                    },
                    "easing": "cubic_in_out",
                    "value": 0.0
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 5000
                    },
                    "easing": "cubic_in_out",
                    "value": 0.0
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 5250
                    },
                    "easing": "cubic_in_out",
                    "value": 0.8
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 9000
                    },
                    "easing": "cubic_in_out",
                    "value": 0.4
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 11500
                    },
                    "easing": "cubic_in_out",
                    "value": 0.0
                  }
                ]
              }
            ],
            "id": "diagonal",
            "parent_id": null,
            "space": "screen",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "shape",
            "params": {
              "geometry": {
                "kind": "polygon",
                "points": [
                  [
                    0.0,
                    1400.0
                  ],
                  [
                    1080.0,
                    1100.0
                  ],
                  [
                    1080.0,
                    1200.0
                  ],
                  [
                    0.0,
                    1500.0
                  ]
                ]
              },
              "fill": {
                "kind": "dna_palette",
                "index": 2
              },
              "stroke": null,
              "stroke_width": 1.0,
              "draw_progress": 1.0
            }
          },
          {
            "position": [
              0.0,
              0.0,
              0.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [
              {
                "property": "progress",
                "keyframes": [
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 0
                    },
                    "easing": "cubic_in_out",
                    "value": 0.0
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 300
                    },
                    "easing": "cubic_out",
                    "value": 1.0
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 11500
                    },
                    "easing": "cubic_in_out",
                    "value": 1.0
                  }
                ]
              }
            ],
            "id": "cut-mask",
            "parent_id": null,
            "space": "screen",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "mask",
            "params": {
              "target_id": "hero",
              "geometry": {
                "kind": "polygon",
                "points": [
                  [
                    0.0,
                    0.0
                  ],
                  [
                    1080.0,
                    0.0
                  ],
                  [
                    1080.0,
                    1920.0
                  ],
                  [
                    0.0,
                    1920.0
                  ]
                ]
              },
              "progress": 1.0
            }
          }
        ],
        "cues": [
          {
            "id": "impact",
            "at_ms": 0,
            "sound": {
              "asset_binding": "score",
              "source_in_ms": 0,
              "duration_ms": 12000,
              "gain": 0.8,
              "fade_in_ms": 5,
              "fade_out_ms": 350
            }
          },
          {
            "id": "cut",
            "at_ms": 5000,
            "sound": null
          },
          {
            "id": "resolve",
            "at_ms": 9000,
            "sound": null
          }
        ]
      }
    }
  ]
} satisfies MotionComposition;
export const music = {
  "schema_version": "motion_composition_v1",
  "project_id": "fixture-music",
  "expected": {
    "storyboard_revision": 1,
    "snapshot_sha256": "c3ec21b22ea3b821c9f0ac2ce024b484593578dab65e65a1b15a49b2622f5c1b",
    "canvas": {
      "width": 1080,
      "height": 1080,
      "fps_num": 30,
      "fps_den": 1
    },
    "duration_ms": 10000
  },
  "recipe": {
    "id": "music.orbital-sleeve",
    "version": "1.0.0",
    "sha256": "c36e17f249d0fb343ec6f79b2f8ee1b29190aac6824a9f50f373572dcad47d2f"
  },
  "asset_bindings": {
    "score": {
      "asset_id": "fixture-music-score",
      "sha256": "0cd4af6512b87e9ad5da741b7e5adbae9d8c5f614414e64b8da34d11043b65ca",
      "byte_size": 1024,
      "kind": "audio",
      "duration_ms": 10000,
      "sample_rate": 48000,
      "channels": 2
    },
    "cover": {
      "asset_id": "fixture-music-cover",
      "sha256": "d263282c189db68d014aa1ed4dd61ee18d55eaaebfc1cfc5f54e7c924f457459",
      "byte_size": 1024,
      "kind": "image",
      "width": 512,
      "height": 512
    }
  },
  "scenes": [
    {
      "shot_id": "main",
      "graph": {
        "schema_version": "motion_scene_v1",
        "safe_area": {
          "left": 72,
          "right": 72,
          "top": 72,
          "bottom": 72
        },
        "camera": {
          "position": [
            0.0,
            0.0,
            0.0
          ],
          "rotate_z": 0.0,
          "focal_length": 1400.0,
          "animations": [
            {
              "property": "position",
              "keyframes": [
                {
                  "time": {
                    "kind": "ms",
                    "at_ms": 0
                  },
                  "easing": "cubic_in_out",
                  "value": [
                    -80.0,
                    0.0,
                    0.0
                  ]
                },
                {
                  "time": {
                    "kind": "ms",
                    "at_ms": 5000
                  },
                  "easing": "cubic_in_out",
                  "value": [
                    80.0,
                    0.0,
                    120.0
                  ]
                },
                {
                  "time": {
                    "kind": "ms",
                    "at_ms": 9500
                  },
                  "easing": "cubic_in_out",
                  "value": [
                    0.0,
                    0.0,
                    0.0
                  ]
                }
              ]
            }
          ]
        },
        "nodes": [
          {
            "position": [
              540.0,
              540.0,
              400.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [
              {
                "property": "rotate_z",
                "keyframes": [
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 0
                    },
                    "easing": "cubic_in_out",
                    "value": -24.0
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 9500
                    },
                    "easing": "cubic_in_out",
                    "value": 36.0
                  }
                ]
              }
            ],
            "id": "orbit",
            "parent_id": null,
            "space": "world",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "group"
          },
          {
            "position": [
              -420.0,
              -420.0,
              0.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [
              {
                "property": "scale",
                "keyframes": [
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 0
                    },
                    "easing": "cubic_in_out",
                    "value": [
                      0.9,
                      0.9
                    ]
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 2500
                    },
                    "easing": "cubic_in_out",
                    "value": [
                      1.0,
                      1.0
                    ]
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 5000
                    },
                    "easing": "cubic_in_out",
                    "value": [
                      0.92,
                      0.92
                    ]
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 7500
                    },
                    "easing": "cubic_in_out",
                    "value": [
                      1.02,
                      1.02
                    ]
                  }
                ]
              }
            ],
            "id": "ring",
            "parent_id": "orbit",
            "space": "world",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "shape",
            "params": {
              "geometry": {
                "kind": "ellipse",
                "width": 840.0,
                "height": 840.0
              },
              "fill": null,
              "stroke": {
                "kind": "dna_palette",
                "index": 2
              },
              "stroke_width": 6.0,
              "draw_progress": 1.0
            }
          },
          {
            "position": [
              -400.0,
              -400.0,
              0.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [],
            "id": "orbital-text",
            "parent_id": "orbit",
            "space": "world",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "text",
            "params": {
              "text": {
                "kind": "shot_field",
                "field": "on_screen_text"
              },
              "font": {
                "kind": "dna_font",
                "index": 0
              },
              "fill": {
                "kind": "dna_palette",
                "index": 1
              },
              "size": 64.0,
              "max_width": 800.0,
              "line_height": 1.0,
              "max_lines": 6,
              "align": "left",
              "method": "fade_slide"
            }
          },
          {
            "position": [
              310.0,
              280.0,
              0.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [
              {
                "property": "scale",
                "keyframes": [
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 0
                    },
                    "easing": "cubic_in_out",
                    "value": [
                      0.9,
                      0.9
                    ]
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 900
                    },
                    "easing": "cubic_in_out",
                    "value": [
                      1.0,
                      1.0
                    ]
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 7500
                    },
                    "easing": "cubic_in_out",
                    "value": [
                      1.04,
                      1.04
                    ]
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 9500
                    },
                    "easing": "cubic_in_out",
                    "value": [
                      1.0,
                      1.0
                    ]
                  }
                ]
              }
            ],
            "id": "sleeve",
            "parent_id": null,
            "space": "world",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "image",
            "params": {
              "asset_binding": "cover",
              "width": 460.0,
              "height": 460.0,
              "fit": "contain"
            }
          },
          {
            "position": [
              90.0,
              850.0,
              0.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [
              {
                "property": "opacity",
                "keyframes": [
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 0
                    },
                    "easing": "hold",
                    "value": 0.0
                  },
                  {
                    "time": {
                      "kind": "cue",
                      "cue_ref": "phrase",
                      "offset_ms": 0
                    },
                    "easing": "linear",
                    "value": 0.0
                  },
                  {
                    "time": {
                      "kind": "cue",
                      "cue_ref": "phrase",
                      "offset_ms": 400
                    },
                    "easing": "cubic_out",
                    "value": 1.0
                  }
                ]
              }
            ],
            "id": "front-title",
            "parent_id": null,
            "space": "screen",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "text",
            "params": {
              "text": {
                "kind": "shot_field",
                "field": "on_screen_text"
              },
              "font": {
                "kind": "dna_font",
                "index": 0
              },
              "fill": {
                "kind": "dna_palette",
                "index": 1
              },
              "size": 84.0,
              "max_width": 900.0,
              "line_height": 1.0,
              "max_lines": 6,
              "align": "left",
              "method": "fade_slide"
            }
          }
        ],
        "cues": [
          {
            "id": "score",
            "at_ms": 0,
            "sound": {
              "asset_binding": "score",
              "source_in_ms": 0,
              "duration_ms": 10000,
              "gain": 0.75,
              "fade_in_ms": 80,
              "fade_out_ms": 500
            }
          },
          {
            "id": "pulse",
            "at_ms": 2500,
            "sound": null
          },
          {
            "id": "phrase",
            "at_ms": 5000,
            "sound": null
          },
          {
            "id": "resolve",
            "at_ms": 7500,
            "sound": null
          }
        ]
      }
    }
  ]
} satisfies MotionComposition;
export const geo = {
  "schema_version": "motion_composition_v1",
  "project_id": "fixture-geo",
  "expected": {
    "storyboard_revision": 1,
    "snapshot_sha256": "207f44d954f8ec124aefd084baf6a1e50ba381bb2b820b5955a5c2abba0b98f5",
    "canvas": {
      "width": 1920,
      "height": 1080,
      "fps_num": 30,
      "fps_den": 1
    },
    "duration_ms": 15000
  },
  "recipe": {
    "id": "geo.route-explainer",
    "version": "1.0.0",
    "sha256": "9d0f1d3dcf0556b9b89a6a8b47a617a4e85b1e926e2e874839161e6905a2859d"
  },
  "asset_bindings": {
    "score": {
      "asset_id": "fixture-geo-score",
      "sha256": "ea24fad2d045f5a2c8aa2a1cca3b8de4a898d0fe0b67695456048c0cd4820e8e",
      "byte_size": 1024,
      "kind": "audio",
      "duration_ms": 15000,
      "sample_rate": 48000,
      "channels": 2
    }
  },
  "scenes": [
    {
      "shot_id": "main",
      "graph": {
        "schema_version": "motion_scene_v1",
        "safe_area": {
          "left": 100,
          "right": 100,
          "top": 80,
          "bottom": 100
        },
        "camera": {
          "position": [
            0.0,
            0.0,
            0.0
          ],
          "rotate_z": 0.0,
          "focal_length": 1600.0,
          "animations": [
            {
              "property": "position",
              "keyframes": [
                {
                  "time": {
                    "kind": "ms",
                    "at_ms": 0
                  },
                  "easing": "cubic_in_out",
                  "value": [
                    -100.0,
                    0.0,
                    0.0
                  ]
                },
                {
                  "time": {
                    "kind": "ms",
                    "at_ms": 6500
                  },
                  "easing": "cubic_in_out",
                  "value": [
                    200.0,
                    80.0,
                    180.0
                  ]
                },
                {
                  "time": {
                    "kind": "ms",
                    "at_ms": 13000
                  },
                  "easing": "cubic_in_out",
                  "value": [
                    0.0,
                    0.0,
                    0.0
                  ]
                }
              ]
            }
          ]
        },
        "nodes": [
          {
            "position": [
              100.0,
              120.0,
              300.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [],
            "id": "map",
            "parent_id": null,
            "space": "world",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "group"
          },
          {
            "position": [
              0.0,
              0.0,
              0.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [],
            "id": "region",
            "parent_id": "map",
            "space": "world",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "shape",
            "params": {
              "geometry": {
                "kind": "polygon",
                "points": [
                  [
                    0.0,
                    80.0
                  ],
                  [
                    700.0,
                    0.0
                  ],
                  [
                    1500.0,
                    280.0
                  ],
                  [
                    1420.0,
                    720.0
                  ],
                  [
                    600.0,
                    800.0
                  ],
                  [
                    80.0,
                    520.0
                  ]
                ]
              },
              "fill": {
                "kind": "dna_palette",
                "index": 0
              },
              "stroke": {
                "kind": "dna_palette",
                "index": 1
              },
              "stroke_width": 3.0,
              "draw_progress": 1.0
            }
          },
          {
            "position": [
              0.0,
              0.0,
              0.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [
              {
                "property": "draw_progress",
                "keyframes": [
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 1500
                    },
                    "easing": "cubic_in_out",
                    "value": 0.0
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 9000
                    },
                    "easing": "cubic_in_out",
                    "value": 1.0
                  }
                ]
              }
            ],
            "id": "route",
            "parent_id": "map",
            "space": "world",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "shape",
            "params": {
              "geometry": {
                "kind": "polyline",
                "points": [
                  [
                    180.0,
                    520.0
                  ],
                  [
                    420.0,
                    430.0
                  ],
                  [
                    700.0,
                    460.0
                  ],
                  [
                    1050.0,
                    220.0
                  ],
                  [
                    1360.0,
                    280.0
                  ]
                ]
              },
              "fill": null,
              "stroke": {
                "kind": "dna_palette",
                "index": 2
              },
              "stroke_width": 12.0,
              "draw_progress": 0.0
            }
          },
          {
            "position": [
              0.0,
              0.0,
              0.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [
              {
                "property": "progress",
                "keyframes": [
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 1500
                    },
                    "easing": "cubic_in_out",
                    "value": 0.0
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 9000
                    },
                    "easing": "cubic_in_out",
                    "value": 1.0
                  }
                ]
              }
            ],
            "id": "marker",
            "parent_id": "map",
            "space": "world",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "path_follower",
            "params": {
              "path_ref": "route",
              "progress": 0.0,
              "marker": {
                "kind": "ellipse",
                "width": 28.0,
                "height": 28.0
              },
              "fill": {
                "kind": "dna_palette",
                "index": 1
              }
            }
          },
          {
            "position": [
              110.0,
              85.0,
              0.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [],
            "id": "heading",
            "parent_id": null,
            "space": "screen",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "text",
            "params": {
              "text": {
                "kind": "shot_field",
                "field": "on_screen_text"
              },
              "font": {
                "kind": "dna_font",
                "index": 0
              },
              "fill": {
                "kind": "dna_palette",
                "index": 1
              },
              "size": 72.0,
              "max_width": 1600.0,
              "line_height": 1.0,
              "max_lines": 6,
              "align": "left",
              "method": "fade_slide"
            }
          },
          {
            "position": [
              110.0,
              930.0,
              0.0
            ],
            "scale": [
              1.0,
              1.0
            ],
            "rotate_z": 0.0,
            "opacity": 1.0,
            "animations": [
              {
                "property": "opacity",
                "keyframes": [
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 0
                    },
                    "easing": "cubic_in_out",
                    "value": 0.0
                  },
                  {
                    "time": {
                      "kind": "ms",
                      "at_ms": 800
                    },
                    "easing": "cubic_in_out",
                    "value": 1.0
                  }
                ]
              }
            ],
            "id": "source",
            "parent_id": null,
            "space": "screen",
            "z_index": 0,
            "anchor": [
              0.0,
              0.0
            ],
            "active_ms": null,
            "type": "text",
            "params": {
              "text": {
                "kind": "approved_claim_field",
                "claim_id": "fixture-geo-claim",
                "field": "source_label"
              },
              "font": {
                "kind": "dna_font",
                "index": 0
              },
              "fill": {
                "kind": "dna_palette",
                "index": 1
              },
              "size": 36.0,
              "max_width": 1600.0,
              "line_height": 1.0,
              "max_lines": 6,
              "align": "left",
              "method": "fade_slide"
            }
          }
        ],
        "cues": [
          {
            "id": "ambience",
            "at_ms": 0,
            "sound": {
              "asset_binding": "score",
              "source_in_ms": 0,
              "duration_ms": 15000,
              "gain": 0.6,
              "fade_in_ms": 300,
              "fade_out_ms": 800
            }
          },
          {
            "id": "start-route",
            "at_ms": 1500,
            "sound": null
          },
          {
            "id": "arrival",
            "at_ms": 9000,
            "sound": null
          }
        ]
      }
    }
  ]
} satisfies MotionComposition;
