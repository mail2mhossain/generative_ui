namespace BlazorAGUIDemo.Components.Blocks;

/// <summary>
/// Parameters for the PageTitle declarative block.
/// Renders a bold section heading with an optional subtitle.
/// </summary>
public class PageTitleParams
{
    /// <summary>Primary heading text.</summary>
    public string Text { get; set; } = string.Empty;

    /// <summary>Optional secondary line shown below the heading.</summary>
    public string Subtitle { get; set; } = string.Empty;
}
