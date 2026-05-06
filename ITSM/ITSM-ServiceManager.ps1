Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Global:Services = @{}
$Global:LogBuffers = @{}
$Global:StartTimes = @{}
$Global:ServiceDefs = @(
    @{ Name="FastAPI Web Server"; Key="fastapi"; Exe="venv\Scripts\python.exe"; Args="-m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"; WorkDir=$scriptRoot; Delay=0 },
    @{ Name="Network Telemetry"; Key="telemetry"; Exe="venv\Scripts\python.exe"; Args="scripts\network_telemetry_worker.py"; WorkDir=$scriptRoot; Delay=5 },
    @{ Name="Asset Inventory Sync"; Key="assets"; Exe="powershell.exe"; Args="-ExecutionPolicy Bypass -File scripts\Sync-ITSMAssets.ps1"; WorkDir=$scriptRoot; Delay=0 },
    @{ Name="Printer Inventory Sync"; Key="printers"; Exe="powershell.exe"; Args="-ExecutionPolicy Bypass -File scripts\Sync-ITSMPrinters.ps1"; WorkDir=$scriptRoot; Delay=0 }
)
foreach ($s in $Global:ServiceDefs) { $Global:LogBuffers[$s.Key] = [System.Collections.ArrayList]::new() }
[xml]$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="ITSM Service Manager" Width="1300" Height="900" MinWidth="1000" MinHeight="700"
        WindowStartupLocation="CenterScreen" Background="#0A0E17" FontFamily="Segoe UI"
        WindowStyle="None" AllowsTransparency="True">
    
    <Window.Resources>
        <SolidColorBrush x:Key="BgColor" Color="#0A0E17"/>
        <SolidColorBrush x:Key="PanelColor" Color="#111827"/>
        <SolidColorBrush x:Key="BorderColor" Color="#1F2937"/>
        <SolidColorBrush x:Key="TextPrimary" Color="#F9FAFB"/>
        <SolidColorBrush x:Key="TextSecondary" Color="#9CA3AF"/>
        <SolidColorBrush x:Key="AccentBlue" Color="#3B82F6"/>
        <SolidColorBrush x:Key="AccentGreen" Color="#10B981"/>
        <SolidColorBrush x:Key="AccentRed" Color="#EF4444"/>

        <!-- Custom ScrollBar -->
        <Style TargetType="ScrollBar">
            <Setter Property="Background" Value="Transparent"/>
            <Setter Property="Width" Value="8"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="ScrollBar">
                        <Border Background="{TemplateBinding Background}">
                            <Track x:Name="PART_Track" IsDirectionReversed="true">
                                <Track.Thumb>
                                    <Thumb>
                                        <Thumb.Template>
                                            <ControlTemplate TargetType="Thumb">
                                                <Border Background="#374151" CornerRadius="4" Margin="2"/>
                                            </ControlTemplate>
                                        </Thumb.Template>
                                    </Thumb>
                                </Track.Thumb>
                            </Track>
                        </Border>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>

        <!-- Professional Button -->
        <Style x:Key="ProBtn" TargetType="Button">
            <Setter Property="Background" Value="#1F2937"/>
            <Setter Property="Foreground" Value="#F9FAFB"/>
            <Setter Property="BorderThickness" Value="1"/>
            <Setter Property="BorderBrush" Value="#374151"/>
            <Setter Property="Padding" Value="15,8"/>
            <Setter Property="Cursor" Value="Hand"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="Button">
                        <Border Background="{TemplateBinding Background}" CornerRadius="6" 
                                BorderThickness="{TemplateBinding BorderThickness}" 
                                BorderBrush="{TemplateBinding BorderBrush}">
                            <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
                        </Border>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
            <Style.Triggers>
                <Trigger Property="IsMouseOver" Value="True">
                    <Setter Property="Background" Value="#374151"/>
                </Trigger>
            </Style.Triggers>
        </Style>

        <!-- Action Buttons -->
        <Style x:Key="StartBtn" TargetType="Button" BasedOn="{StaticResource ProBtn}">
            <Setter Property="Background" Value="#064E3B"/>
            <Setter Property="BorderBrush" Value="#059669"/>
            <Setter Property="Foreground" Value="#A7F3D0"/>
            <Style.Triggers>
                <Trigger Property="IsMouseOver" Value="True">
                    <Setter Property="Background" Value="#047857"/>
                </Trigger>
            </Style.Triggers>
        </Style>

        <Style x:Key="StopBtn" TargetType="Button" BasedOn="{StaticResource ProBtn}">
            <Setter Property="Background" Value="#7F1D1D"/>
            <Setter Property="BorderBrush" Value="#DC2626"/>
            <Setter Property="Foreground" Value="#FECACA"/>
            <Style.Triggers>
                <Trigger Property="IsMouseOver" Value="True">
                    <Setter Property="Background" Value="#991B1B"/>
                </Trigger>
            </Style.Triggers>
        </Style>
        
        <!-- Card Style -->
        <Style x:Key="CardStyle" TargetType="Border">
            <Setter Property="Background" Value="{StaticResource PanelColor}"/>
            <Setter Property="CornerRadius" Value="12"/>
            <Setter Property="BorderThickness" Value="1"/>
            <Setter Property="BorderBrush" Value="{StaticResource BorderColor}"/>
            <Setter Property="Effect">
                <Setter.Value>
                    <DropShadowEffect BlurRadius="15" ShadowDepth="4" Opacity="0.15" Color="Black"/>
                </Setter.Value>
            </Setter>
        </Style>
    </Window.Resources>

    <Border CornerRadius="12" Background="{StaticResource BgColor}" BorderThickness="1" BorderBrush="#1F2937">
        <Grid>
            <Grid.RowDefinitions>
                <RowDefinition Height="60"/>
                <RowDefinition Height="Auto"/>
                <RowDefinition Height="Auto"/>
                <RowDefinition Height="*"/>
            </Grid.RowDefinitions>

            <!-- CUSTOM TITLE BAR -->
            <Border x:Name="TitleBar" Grid.Row="0" Background="#111827" CornerRadius="12,12,0,0" BorderThickness="0,0,0,1" BorderBrush="#1F2937">
                <Grid>
                    <Grid.ColumnDefinitions>
                        <ColumnDefinition Width="Auto"/>
                        <ColumnDefinition Width="*"/>
                        <ColumnDefinition Width="Auto"/>
                    </Grid.ColumnDefinitions>
                    
                    <!-- Logo / Title -->
                    <StackPanel Grid.Column="0" Orientation="Horizontal" VerticalAlignment="Center" Margin="20,0,0,0">
                        <Border Background="#3B82F6" CornerRadius="8" Width="32" Height="32" Margin="0,0,15,0">
                            <TextBlock Text="âš¡" FontSize="18" Foreground="White" HorizontalAlignment="Center" VerticalAlignment="Center"/>
                        </Border>
                        <TextBlock Text="ITSM" Foreground="White" FontSize="20" FontWeight="Bold" VerticalAlignment="Center"/>
                        <TextBlock Text=" Service Manager" Foreground="#9CA3AF" FontSize="20" FontWeight="Light" VerticalAlignment="Center"/>
                    </StackPanel>

                    <!-- Global Controls -->
                    <StackPanel Grid.Column="2" Orientation="Horizontal" VerticalAlignment="Center" Margin="0,0,20,0">
                        <Button x:Name="btnStartAll" Content="â–¶ Start All Services" Style="{StaticResource StartBtn}" Margin="0,0,10,0"/>
                        <Button x:Name="btnStopAll" Content="â¹ Stop All" Style="{StaticResource StopBtn}" Margin="0,0,20,0"/>
                        <Button x:Name="btnMinimize" Content="â€”" Style="{StaticResource ProBtn}" Width="40" Padding="0"/>
                        <Button x:Name="btnClose" Content="âœ•" Style="{StaticResource StopBtn}" Width="40" Margin="10,0,0,0" Padding="0"/>
                    </StackPanel>
                </Grid>
            </Border>

            <!-- GLOBAL METRICS -->
            <Border Grid.Row="1" Margin="20,20,20,10" Style="{StaticResource CardStyle}">
                <Grid Margin="20">
                    <Grid.ColumnDefinitions>
                        <ColumnDefinition Width="*"/>
                        <ColumnDefinition Width="1"/>
                        <ColumnDefinition Width="*"/>
                        <ColumnDefinition Width="1"/>
                        <ColumnDefinition Width="*"/>
                    </Grid.ColumnDefinitions>

                    <StackPanel Grid.Column="0" HorizontalAlignment="Center">
                        <TextBlock Text="SYSTEM CPU &amp; RAM" Foreground="{StaticResource TextSecondary}" FontSize="12" FontWeight="SemiBold" Margin="0,0,0,8" HorizontalAlignment="Center"/>
                        <StackPanel Orientation="Horizontal" HorizontalAlignment="Center">
                            <TextBlock x:Name="txtSysCpu" Text="0%" Foreground="White" FontSize="28" FontWeight="Light"/>
                            <TextBlock Text=" / " Foreground="#4B5563" FontSize="28" FontWeight="Light"/>
                            <TextBlock x:Name="txtSysRam" Text="0GB" Foreground="White" FontSize="28" FontWeight="Light"/>
                        </StackPanel>
                    </StackPanel>

                    <Rectangle Grid.Column="1" Fill="{StaticResource BorderColor}" Margin="0,5"/>

                    <StackPanel Grid.Column="2" HorizontalAlignment="Center">
                        <TextBlock Text="ITSM SERVICES LOAD" Foreground="{StaticResource TextSecondary}" FontSize="12" FontWeight="SemiBold" Margin="0,0,0,8" HorizontalAlignment="Center"/>
                        <StackPanel Orientation="Horizontal" HorizontalAlignment="Center">
                            <TextBlock x:Name="txtItsmCpu" Text="0%" Foreground="#60A5FA" FontSize="28" FontWeight="Light"/>
                            <TextBlock Text=" / " Foreground="#4B5563" FontSize="28" FontWeight="Light"/>
                            <TextBlock x:Name="txtItsmRam" Text="0MB" Foreground="#60A5FA" FontSize="28" FontWeight="Light"/>
                        </StackPanel>
                    </StackPanel>

                    <Rectangle Grid.Column="3" Fill="{StaticResource BorderColor}" Margin="0,5"/>

                    <StackPanel Grid.Column="4" HorizontalAlignment="Center">
                        <TextBlock Text="NETWORK THROUGHPUT" Foreground="{StaticResource TextSecondary}" FontSize="12" FontWeight="SemiBold" Margin="0,0,0,8" HorizontalAlignment="Center"/>
                        <StackPanel Orientation="Horizontal" HorizontalAlignment="Center">
                            <TextBlock Text="â–² " Foreground="#10B981" FontSize="20" VerticalAlignment="Center"/>
                            <TextBlock x:Name="txtNetSent" Text="0 KB/s" Foreground="White" FontSize="24" FontWeight="Light" VerticalAlignment="Center" Margin="0,0,15,0"/>
                            <TextBlock Text="â–¼ " Foreground="#3B82F6" FontSize="20" VerticalAlignment="Center"/>
                            <TextBlock x:Name="txtNetRecv" Text="0 KB/s" Foreground="White" FontSize="24" FontWeight="Light" VerticalAlignment="Center"/>
                        </StackPanel>
                    </StackPanel>
                </Grid>
            </Border>

            <!-- SERVICE CARDS -->
            <Grid Grid.Row="2" Margin="10,0,10,0">
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="*"/>
                </Grid.ColumnDefinitions>

                <!-- FastAPI -->
                <Border Grid.Column="0" Margin="10" Style="{StaticResource CardStyle}">
                    <StackPanel Margin="15">
                        <Grid>
                            <Grid.ColumnDefinitions>
                                <ColumnDefinition Width="Auto"/>
                                <ColumnDefinition Width="*"/>
                                <ColumnDefinition Width="Auto"/>
                            </Grid.ColumnDefinitions>
                            <TextBlock Grid.Column="0" Text="ðŸŒ" FontSize="24" Margin="0,0,10,0"/>
                            <TextBlock Grid.Column="1" Text="FastAPI Web Server" Foreground="White" FontSize="15" FontWeight="SemiBold" VerticalAlignment="Center"/>
                            <Border Grid.Column="2" Background="#1F2937" CornerRadius="12" Padding="8,4" VerticalAlignment="Center">
                                <StackPanel Orientation="Horizontal">
                                    <Ellipse x:Name="indFastapi" Width="8" Height="8" Fill="{StaticResource AccentRed}" Margin="0,0,6,0" VerticalAlignment="Center"/>
                                    <TextBlock x:Name="statFastapi" Text="Stopped" Foreground="{StaticResource TextSecondary}" FontSize="11" FontWeight="SemiBold" VerticalAlignment="Center"/>
                                </StackPanel>
                            </Border>
                        </Grid>
                        
                        <Grid Margin="0,20,0,15">
                            <Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition/><ColumnDefinition/></Grid.ColumnDefinitions>
                            <StackPanel Grid.Column="0">
                                <TextBlock Text="CPU" Foreground="{StaticResource TextSecondary}" FontSize="10" Margin="0,0,0,2"/>
                                <TextBlock x:Name="cpuFastapi" Text="-" Foreground="White" FontSize="16" FontWeight="SemiBold"/>
                            </StackPanel>
                            <StackPanel Grid.Column="1">
                                <TextBlock Text="RAM" Foreground="{StaticResource TextSecondary}" FontSize="10" Margin="0,0,0,2"/>
                                <TextBlock x:Name="ramFastapi" Text="-" Foreground="White" FontSize="16" FontWeight="SemiBold"/>
                            </StackPanel>
                            <StackPanel Grid.Column="2">
                                <TextBlock Text="PID" Foreground="{StaticResource TextSecondary}" FontSize="10" Margin="0,0,0,2"/>
                                <TextBlock x:Name="pidFastapi" Text="-" Foreground="White" FontSize="16" FontWeight="SemiBold"/>
                            </StackPanel>
                        </Grid>
                        
                        <TextBlock x:Name="uptimeFastapi" Text="Uptime: -" Foreground="{StaticResource TextSecondary}" FontSize="11" Margin="0,0,0,15"/>
                        
                        <UniformGrid Columns="3">
                            <Button x:Name="btnStartFastapi" Content="â–¶" Style="{StaticResource ProBtn}" Margin="0,0,5,0"/>
                            <Button x:Name="btnStopFastapi" Content="â¹" Style="{StaticResource ProBtn}" Margin="0,0,5,0"/>
                            <Button x:Name="btnRestartFastapi" Content="â†»" Style="{StaticResource ProBtn}"/>
                        </UniformGrid>
                    </StackPanel>
                </Border>

                <!-- Telemetry -->
                <Border Grid.Column="1" Margin="10" Style="{StaticResource CardStyle}">
                    <StackPanel Margin="15">
                        <Grid>
                            <Grid.ColumnDefinitions>
                                <ColumnDefinition Width="Auto"/>
                                <ColumnDefinition Width="*"/>
                                <ColumnDefinition Width="Auto"/>
                            </Grid.ColumnDefinitions>
                            <TextBlock Grid.Column="0" Text="ðŸ“¡" FontSize="24" Margin="0,0,10,0"/>
                            <TextBlock Grid.Column="1" Text="Network Telemetry" Foreground="White" FontSize="15" FontWeight="SemiBold" VerticalAlignment="Center"/>
                            <Border Grid.Column="2" Background="#1F2937" CornerRadius="12" Padding="8,4" VerticalAlignment="Center">
                                <StackPanel Orientation="Horizontal">
                                    <Ellipse x:Name="indTelemetry" Width="8" Height="8" Fill="{StaticResource AccentRed}" Margin="0,0,6,0" VerticalAlignment="Center"/>
                                    <TextBlock x:Name="statTelemetry" Text="Stopped" Foreground="{StaticResource TextSecondary}" FontSize="11" FontWeight="SemiBold" VerticalAlignment="Center"/>
                                </StackPanel>
                            </Border>
                        </Grid>
                        
                        <Grid Margin="0,20,0,15">
                            <Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition/><ColumnDefinition/></Grid.ColumnDefinitions>
                            <StackPanel Grid.Column="0">
                                <TextBlock Text="CPU" Foreground="{StaticResource TextSecondary}" FontSize="10" Margin="0,0,0,2"/>
                                <TextBlock x:Name="cpuTelemetry" Text="-" Foreground="White" FontSize="16" FontWeight="SemiBold"/>
                            </StackPanel>
                            <StackPanel Grid.Column="1">
                                <TextBlock Text="RAM" Foreground="{StaticResource TextSecondary}" FontSize="10" Margin="0,0,0,2"/>
                                <TextBlock x:Name="ramTelemetry" Text="-" Foreground="White" FontSize="16" FontWeight="SemiBold"/>
                            </StackPanel>
                            <StackPanel Grid.Column="2">
                                <TextBlock Text="PID" Foreground="{StaticResource TextSecondary}" FontSize="10" Margin="0,0,0,2"/>
                                <TextBlock x:Name="pidTelemetry" Text="-" Foreground="White" FontSize="16" FontWeight="SemiBold"/>
                            </StackPanel>
                        </Grid>
                        
                        <TextBlock x:Name="uptimeTelemetry" Text="Uptime: -" Foreground="{StaticResource TextSecondary}" FontSize="11" Margin="0,0,0,15"/>
                        
                        <UniformGrid Columns="3">
                            <Button x:Name="btnStartTelemetry" Content="â–¶" Style="{StaticResource ProBtn}" Margin="0,0,5,0"/>
                            <Button x:Name="btnStopTelemetry" Content="â¹" Style="{StaticResource ProBtn}" Margin="0,0,5,0"/>
                            <Button x:Name="btnRestartTelemetry" Content="â†»" Style="{StaticResource ProBtn}"/>
                        </UniformGrid>
                    </StackPanel>
                </Border>

                <!-- Assets -->
                <Border Grid.Column="2" Margin="10" Style="{StaticResource CardStyle}">
                    <StackPanel Margin="15">
                        <Grid>
                            <Grid.ColumnDefinitions>
                                <ColumnDefinition Width="Auto"/>
                                <ColumnDefinition Width="*"/>
                                <ColumnDefinition Width="Auto"/>
                            </Grid.ColumnDefinitions>
                            <TextBlock Grid.Column="0" Text="ðŸ’»" FontSize="24" Margin="0,0,10,0"/>
                            <TextBlock Grid.Column="1" Text="Asset Inventory" Foreground="White" FontSize="15" FontWeight="SemiBold" VerticalAlignment="Center"/>
                            <Border Grid.Column="2" Background="#1F2937" CornerRadius="12" Padding="8,4" VerticalAlignment="Center">
                                <StackPanel Orientation="Horizontal">
                                    <Ellipse x:Name="indAssets" Width="8" Height="8" Fill="{StaticResource AccentRed}" Margin="0,0,6,0" VerticalAlignment="Center"/>
                                    <TextBlock x:Name="statAssets" Text="Stopped" Foreground="{StaticResource TextSecondary}" FontSize="11" FontWeight="SemiBold" VerticalAlignment="Center"/>
                                </StackPanel>
                            </Border>
                        </Grid>
                        
                        <Grid Margin="0,20,0,15">
                            <Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition/><ColumnDefinition/></Grid.ColumnDefinitions>
                            <StackPanel Grid.Column="0">
                                <TextBlock Text="CPU" Foreground="{StaticResource TextSecondary}" FontSize="10" Margin="0,0,0,2"/>
                                <TextBlock x:Name="cpuAssets" Text="-" Foreground="White" FontSize="16" FontWeight="SemiBold"/>
                            </StackPanel>
                            <StackPanel Grid.Column="1">
                                <TextBlock Text="RAM" Foreground="{StaticResource TextSecondary}" FontSize="10" Margin="0,0,0,2"/>
                                <TextBlock x:Name="ramAssets" Text="-" Foreground="White" FontSize="16" FontWeight="SemiBold"/>
                            </StackPanel>
                            <StackPanel Grid.Column="2">
                                <TextBlock Text="PID" Foreground="{StaticResource TextSecondary}" FontSize="10" Margin="0,0,0,2"/>
                                <TextBlock x:Name="pidAssets" Text="-" Foreground="White" FontSize="16" FontWeight="SemiBold"/>
                            </StackPanel>
                        </Grid>
                        
                        <TextBlock x:Name="uptimeAssets" Text="Uptime: -" Foreground="{StaticResource TextSecondary}" FontSize="11" Margin="0,0,0,15"/>
                        
                        <UniformGrid Columns="3">
                            <Button x:Name="btnStartAssets" Content="â–¶" Style="{StaticResource ProBtn}" Margin="0,0,5,0"/>
                            <Button x:Name="btnStopAssets" Content="â¹" Style="{StaticResource ProBtn}" Margin="0,0,5,0"/>
                            <Button x:Name="btnRestartAssets" Content="â†»" Style="{StaticResource ProBtn}"/>
                        </UniformGrid>
                    </StackPanel>
                </Border>

                <!-- Printers -->
                <Border Grid.Column="3" Margin="10" Style="{StaticResource CardStyle}">
                    <StackPanel Margin="15">
                        <Grid>
                            <Grid.ColumnDefinitions>
                                <ColumnDefinition Width="Auto"/>
                                <ColumnDefinition Width="*"/>
                                <ColumnDefinition Width="Auto"/>
                            </Grid.ColumnDefinitions>
                            <TextBlock Grid.Column="0" Text="ðŸ–¨ï¸" FontSize="24" Margin="0,0,10,0"/>
                            <TextBlock Grid.Column="1" Text="Printer Inventory" Foreground="White" FontSize="15" FontWeight="SemiBold" VerticalAlignment="Center"/>
                            <Border Grid.Column="2" Background="#1F2937" CornerRadius="12" Padding="8,4" VerticalAlignment="Center">
                                <StackPanel Orientation="Horizontal">
                                    <Ellipse x:Name="indPrinters" Width="8" Height="8" Fill="{StaticResource AccentRed}" Margin="0,0,6,0" VerticalAlignment="Center"/>
                                    <TextBlock x:Name="statPrinters" Text="Stopped" Foreground="{StaticResource TextSecondary}" FontSize="11" FontWeight="SemiBold" VerticalAlignment="Center"/>
                                </StackPanel>
                            </Border>
                        </Grid>
                        
                        <Grid Margin="0,20,0,15">
                            <Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition/><ColumnDefinition/></Grid.ColumnDefinitions>
                            <StackPanel Grid.Column="0">
                                <TextBlock Text="CPU" Foreground="{StaticResource TextSecondary}" FontSize="10" Margin="0,0,0,2"/>
                                <TextBlock x:Name="cpuPrinters" Text="-" Foreground="White" FontSize="16" FontWeight="SemiBold"/>
                            </StackPanel>
                            <StackPanel Grid.Column="1">
                                <TextBlock Text="RAM" Foreground="{StaticResource TextSecondary}" FontSize="10" Margin="0,0,0,2"/>
                                <TextBlock x:Name="ramPrinters" Text="-" Foreground="White" FontSize="16" FontWeight="SemiBold"/>
                            </StackPanel>
                            <StackPanel Grid.Column="2">
                                <TextBlock Text="PID" Foreground="{StaticResource TextSecondary}" FontSize="10" Margin="0,0,0,2"/>
                                <TextBlock x:Name="pidPrinters" Text="-" Foreground="White" FontSize="16" FontWeight="SemiBold"/>
                            </StackPanel>
                        </Grid>
                        
                        <TextBlock x:Name="uptimePrinters" Text="Uptime: -" Foreground="{StaticResource TextSecondary}" FontSize="11" Margin="0,0,0,15"/>
                        
                        <UniformGrid Columns="3">
                            <Button x:Name="btnStartPrinters" Content="â–¶" Style="{StaticResource ProBtn}" Margin="0,0,5,0"/>
                            <Button x:Name="btnStopPrinters" Content="â¹" Style="{StaticResource ProBtn}" Margin="0,0,5,0"/>
                            <Button x:Name="btnRestartPrinters" Content="â†»" Style="{StaticResource ProBtn}"/>
                        </UniformGrid>
                    </StackPanel>
                </Border>
            </Grid>

            <!-- BOTTOM: Users and Logs -->
            <Grid Grid.Row="3" Margin="20,10,20,20">
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="350"/>
                    <ColumnDefinition Width="*"/>
                </Grid.ColumnDefinitions>

                <!-- Users -->
                <Border Grid.Column="0" Style="{StaticResource CardStyle}" Margin="0,0,20,0">
                    <Grid Margin="20">
                        <Grid.RowDefinitions>
                            <RowDefinition Height="Auto"/>
                            <RowDefinition Height="*"/>
                        </Grid.RowDefinitions>
                        
                        <StackPanel Grid.Row="0" Margin="0,0,0,15">
                            <TextBlock Text="ðŸ‘¥ CONNECTED USERS" Foreground="{StaticResource TextSecondary}" FontSize="12" FontWeight="SemiBold" Margin="0,0,0,5"/>
                            <TextBlock x:Name="txtUserCount" Text="0 Active Connections (Port 8000)" Foreground="White" FontSize="16" FontWeight="Light"/>
                        </StackPanel>

                        <ListView x:Name="lvUsers" Grid.Row="1" Background="Transparent" BorderThickness="0" Foreground="White" FontFamily="Consolas" FontSize="12">
                            <ListView.Resources>
                                <Style TargetType="GridViewColumnHeader">
                                    <Setter Property="Background" Value="Transparent"/>
                                    <Setter Property="Foreground" Value="{StaticResource TextSecondary}"/>
                                    <Setter Property="FontFamily" Value="Segoe UI"/>
                                    <Setter Property="FontSize" Value="11"/>
                                    <Setter Property="FontWeight" Value="SemiBold"/>
                                    <Setter Property="Padding" Value="5,0,0,10"/>
                                    <Setter Property="HorizontalContentAlignment" Value="Left"/>
                                    <Setter Property="BorderThickness" Value="0"/>
                                </Style>
                                <Style TargetType="ListViewItem">
                                    <Setter Property="Padding" Value="5,8"/>
                                    <Setter Property="BorderBrush" Value="#1F2937"/>
                                    <Setter Property="BorderThickness" Value="0,0,0,1"/>
                                    <Style.Triggers>
                                        <Trigger Property="IsMouseOver" Value="True">
                                            <Setter Property="Background" Value="#1F2937"/>
                                        </Trigger>
                                    </Style.Triggers>
                                </Style>
                            </ListView.Resources>
                            <ListView.View>
                                <GridView>
                                    <GridViewColumn Header="IP ADDRESS" Width="130" DisplayMemberBinding="{Binding IP}"/>
                                    <GridViewColumn Header="HOST" Width="120" DisplayMemberBinding="{Binding Host}"/>
                                    <GridViewColumn Header="CONN" Width="50" DisplayMemberBinding="{Binding Count}"/>
                                </GridView>
                            </ListView.View>
                        </ListView>
                    </Grid>
                </Border>

                <!-- Logs -->
                <Border Grid.Column="1" Style="{StaticResource CardStyle}">
                    <Grid Margin="20">
                        <Grid.RowDefinitions>
                            <RowDefinition Height="Auto"/>
                            <RowDefinition Height="*"/>
                        </Grid.RowDefinitions>

                        <TextBlock Grid.Row="0" Text="ðŸ“ LIVE LOG OUTPUT" Foreground="{StaticResource TextSecondary}" FontSize="12" FontWeight="SemiBold" Margin="0,0,0,15"/>

                        <TabControl x:Name="logTabs" Grid.Row="1" Background="Transparent" BorderThickness="0" Foreground="White">
                            <TabControl.Resources>
                                <Style TargetType="TabItem">
                                    <Setter Property="Template">
                                        <Setter.Value>
                                            <ControlTemplate TargetType="TabItem">
                                                <Border Name="Border" Background="#111827" BorderBrush="#1F2937" BorderThickness="1,1,1,0" CornerRadius="6,6,0,0" Padding="15,8" Margin="0,0,4,0">
                                                    <ContentPresenter x:Name="ContentSite" VerticalAlignment="Center" HorizontalAlignment="Center" ContentSource="Header"/>
                                                </Border>
                                                <ControlTemplate.Triggers>
                                                    <Trigger Property="IsSelected" Value="True">
                                                        <Setter TargetName="Border" Property="Background" Value="#1F2937"/>
                                                        <Setter TargetName="Border" Property="BorderBrush" Value="#3B82F6"/>
                                                        <Setter Property="Foreground" Value="White"/>
                                                    </Trigger>
                                                    <Trigger Property="IsSelected" Value="False">
                                                        <Setter Property="Foreground" Value="#9CA3AF"/>
                                                    </Trigger>
                                                </ControlTemplate.Triggers>
                                            </ControlTemplate>
                                        </Setter.Value>
                                    </Setter>
                                </Style>
                            </TabControl.Resources>

                            <TabItem Header="FastAPI">
                                <Border Background="#0A0E17" CornerRadius="0,6,6,6" BorderThickness="1" BorderBrush="#1F2937" Padding="15">
                                    <ScrollViewer x:Name="scrollFastapi" VerticalScrollBarVisibility="Auto">
                                        <TextBlock x:Name="logFastapi" TextWrapping="Wrap" Foreground="#A7F3D0" FontFamily="Consolas" FontSize="12"/>
                                    </ScrollViewer>
                                </Border>
                            </TabItem>
                            <TabItem Header="Telemetry">
                                <Border Background="#0A0E17" CornerRadius="0,6,6,6" BorderThickness="1" BorderBrush="#1F2937" Padding="15">
                                    <ScrollViewer x:Name="scrollTelemetry" VerticalScrollBarVisibility="Auto">
                                        <TextBlock x:Name="logTelemetry" TextWrapping="Wrap" Foreground="#93C5FD" FontFamily="Consolas" FontSize="12"/>
                                    </ScrollViewer>
                                </Border>
                            </TabItem>
                            <TabItem Header="Assets">
                                <Border Background="#0A0E17" CornerRadius="0,6,6,6" BorderThickness="1" BorderBrush="#1F2937" Padding="15">
                                    <ScrollViewer x:Name="scrollAssets" VerticalScrollBarVisibility="Auto">
                                        <TextBlock x:Name="logAssets" TextWrapping="Wrap" Foreground="#FDBA74" FontFamily="Consolas" FontSize="12"/>
                                    </ScrollViewer>
                                </Border>
                            </TabItem>
                            <TabItem Header="Printers">
                                <Border Background="#0A0E17" CornerRadius="0,6,6,6" BorderThickness="1" BorderBrush="#1F2937" Padding="15">
                                    <ScrollViewer x:Name="scrollPrinters" VerticalScrollBarVisibility="Auto">
                                        <TextBlock x:Name="logPrinters" TextWrapping="Wrap" Foreground="#D8B4FE" FontFamily="Consolas" FontSize="12"/>
                                    </ScrollViewer>
                                </Border>
                            </TabItem>
                        </TabControl>
                    </Grid>
                </Border>
            </Grid>
        </Grid>
    </Border>
</Window>
"@

$reader = [System.Xml.XmlNodeReader]::new($xaml)
$window = [System.Windows.Markup.XamlReader]::Load($reader)

# Enable dragging for borderless window
$titleBar = $window.FindName("TitleBar")
$titleBar.Add_MouseLeftButtonDown({
    if ($_.ChangedButton -eq 'Left') {
        $window.DragMove()
    }
})

$window.FindName("btnMinimize").Add_Click({ $window.WindowState = 'Minimized' })
$window.FindName("btnClose").Add_Click({ $window.Close() })

$controls = @{}
$xaml.SelectNodes("//*[@*[contains(translate(name(),'X','x'),'x:name') or contains(translate(name(),'N','n'),'name')]]") | ForEach-Object {
    $name = $_.Name; if (-not $name) { $name = $_.'x:Name' }
    if ($name) { $controls[$name] = $window.FindName($name) }
}

function Start-ServiceProcess {
    param([string]$Key)
    $def = $Global:ServiceDefs | Where-Object { $_.Key -eq $Key }
    if (-not $def) { return }
    if ($Global:Services[$Key] -and -not $Global:Services[$Key].HasExited) { return }

    $exePath = Join-Path $def.WorkDir $def.Exe
    if (-not (Test-Path $exePath)) { $exePath = $def.Exe }

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $exePath
    $psi.Arguments = $def.Args
    $psi.WorkingDirectory = $def.WorkDir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    try {
        $proc = [System.Diagnostics.Process]::Start($psi)
        $Global:Services[$Key] = $proc
        $Global:StartTimes[$Key] = Get-Date
        $Global:LogBuffers[$Key].Clear()
        Add-LogLine $Key "Service started (PID: $($proc.Id))"

        Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -Action {
            $k = $Event.MessageData
            if ($EventArgs.Data) {
                $null = $Global:LogBuffers[$k].Add($EventArgs.Data)
                if ($Global:LogBuffers[$k].Count -gt 500) { $Global:LogBuffers[$k].RemoveAt(0) }
            }
        } -MessageData $Key | Out-Null

        Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived -Action {
            $k = $Event.MessageData
            if ($EventArgs.Data) {
                $null = $Global:LogBuffers[$k].Add("[ERR] $($EventArgs.Data)")
                if ($Global:LogBuffers[$k].Count -gt 500) { $Global:LogBuffers[$k].RemoveAt(0) }
            }
        } -MessageData $Key | Out-Null

        $proc.BeginOutputReadLine()
        $proc.BeginErrorReadLine()
    } catch {
        Add-LogLine $Key "FAILED to start: $_"
    }
}

function Stop-ServiceProcess {
    param([string]$Key)
    $proc = $Global:Services[$Key]
    if ($proc -and -not $proc.HasExited) {
        try {
            $pid = $proc.Id
            Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $pid } | ForEach-Object {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }
            $proc.Kill()
            $proc.WaitForExit(3000)
            Add-LogLine $Key "Service stopped."
        } catch {
            Add-LogLine $Key "Error stopping: $_"
        }
    }
    $Global:Services[$Key] = $null
    $Global:StartTimes[$Key] = $null
}

function Restart-ServiceProcess {
    param([string]$Key)
    Add-LogLine $Key "Restarting..."
    Stop-ServiceProcess -Key $Key
    Start-Sleep -Seconds 2
    Start-ServiceProcess -Key $Key
}

function Add-LogLine {
    param([string]$Key, [string]$Msg)
    $ts = (Get-Date).ToString("HH:mm:ss")
    $null = $Global:LogBuffers[$Key].Add("[$ts] $Msg")
    if ($Global:LogBuffers[$Key].Count -gt 500) { $Global:LogBuffers[$Key].RemoveAt(0) }
}

function Format-Bytes {
    param([double]$Bytes)
    if ($Bytes -ge 1MB) { return "{0:N1} MB/s" -f ($Bytes / 1MB) }
    return "{0:N1} KB/s" -f ($Bytes / 1KB)
}

$buttonMap = @{ "fastapi"="Fastapi"; "telemetry"="Telemetry"; "assets"="Assets"; "printers"="Printers" }
foreach ($entry in $buttonMap.GetEnumerator()) {
    $svcKey = $entry.Key; $suffix = $entry.Value
    $startBtn = $window.FindName("btnStart$suffix")
    $stopBtn = $window.FindName("btnStop$suffix")
    $restartBtn = $window.FindName("btnRestart$suffix")
    if ($startBtn)   { $startBtn.Tag = $svcKey;   $startBtn.Add_Click({ Start-ServiceProcess -Key $this.Tag }) }
    if ($stopBtn)    { $stopBtn.Tag = $svcKey;    $stopBtn.Add_Click({ Stop-ServiceProcess -Key $this.Tag }) }
    if ($restartBtn) { $restartBtn.Tag = $svcKey; $restartBtn.Add_Click({ Restart-ServiceProcess -Key $this.Tag }) }
}

$window.FindName("btnStartAll").Add_Click({
    Start-ServiceProcess -Key "fastapi"
    Add-LogLine "fastapi" "Waiting 5s for API to initialize before starting workers..."
    Start-Sleep -Seconds 5
    Start-ServiceProcess -Key "telemetry"
    Start-ServiceProcess -Key "assets"
    Start-ServiceProcess -Key "printers"
})

$window.FindName("btnStopAll").Add_Click({
    foreach ($k in @("printers","assets","telemetry","fastapi")) { Stop-ServiceProcess -Key $k }
})

$Global:PrevBytesSent = 0
$Global:PrevBytesRecv = 0

# Init performance counters for fast tracking
try {
    $Global:CpuCounter = New-Object System.Diagnostics.PerformanceCounter("Processor", "% Processor Time", "_Total")
    $Global:RamCounter = New-Object System.Diagnostics.PerformanceCounter("Memory", "Available MBytes")
    $Global:TotalRamMB = [Math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1MB, 0)
    $Global:TotalRamGB = [Math]::Round($Global:TotalRamMB / 1024, 1)
    $null = $Global:CpuCounter.NextValue() # First call always returns 0
} catch {}

$Global:PrevCpuTime = @{}
$Global:PrevCpuDate = @{}

$metricsTimer = [System.Windows.Threading.DispatcherTimer]::new()
$metricsTimer.Interval = [TimeSpan]::FromSeconds(3)
$metricsTimer.Add_Tick({
    try {
        if ($Global:CpuCounter) {
            $cpuLoad = [Math]::Round($Global:CpuCounter.NextValue(), 1)
            $controls["txtSysCpu"].Text = "$cpuLoad%"
            
            $usedRamMB = $Global:TotalRamMB - $Global:RamCounter.NextValue()
            $usedRamGB = [Math]::Round($usedRamMB / 1024, 1)
            $controls["txtSysRam"].Text = "${usedRamGB}GB / $($Global:TotalRamGB)GB"
        }
    } catch {}

    try {
        $nic = Get-NetAdapterStatistics -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($nic) {
            $sentDelta = $nic.SentBytes - $Global:PrevBytesSent
            $recvDelta = $nic.ReceivedBytes - $Global:PrevBytesRecv
            if ($Global:PrevBytesSent -gt 0) {
                $controls["txtNetSent"].Text = Format-Bytes ($sentDelta / 3)
                $controls["txtNetRecv"].Text = Format-Bytes ($recvDelta / 3)
            }
            $Global:PrevBytesSent = $nic.SentBytes
            $Global:PrevBytesRecv = $nic.ReceivedBytes
        }
    } catch {}

    $totalItsmCpu = 0; $totalItsmRam = 0
    foreach ($key in @("fastapi","telemetry","assets","printers")) {
        $ucKey = $key.Substring(0,1).ToUpper() + $key.Substring(1)
        $proc = $Global:Services[$key]
        $indicator = $controls["ind$ucKey"]
        $statTxt = $controls["stat$ucKey"]
        $cpuCtrl = $controls["cpu$ucKey"]
        $ramCtrl = $controls["ram$ucKey"]
        $pidCtrl = $controls["pid$ucKey"]
        $uptimeCtrl = $controls["uptime$ucKey"]

        if ($proc -and -not $proc.HasExited) {
            try { $proc.Refresh() } catch {}
            $indicator.Fill = [System.Windows.Media.BrushConverter]::new().ConvertFromString("#10B981")
            $statTxt.Text = "Running"
            $statTxt.Foreground = [System.Windows.Media.BrushConverter]::new().ConvertFromString("#10B981")
            $ramMB = [Math]::Round($proc.WorkingSet64 / 1MB, 1)
            $ramCtrl.Text = "$ramMB MB"
            $pidCtrl.Text = "$($proc.Id)"
            $totalItsmRam += $ramMB

            try {
                if (-not $Global:PrevCpuTime[$key]) {
                    $Global:PrevCpuTime[$key] = $proc.TotalProcessorTime
                    $Global:PrevCpuDate[$key] = Get-Date
                    $cpuCtrl.Text = "~"
                } else {
                    $timeDelta = ((Get-Date) - $Global:PrevCpuDate[$key]).TotalSeconds
                    $cpuDelta = ($proc.TotalProcessorTime - $Global:PrevCpuTime[$key]).TotalSeconds
                    if ($timeDelta -gt 0) {
                        $cpuPct = [Math]::Round(($cpuDelta / $timeDelta) * 100 / $env:NUMBER_OF_PROCESSORS, 1)
                        $cpuCtrl.Text = "$cpuPct%"
                        $totalItsmCpu += $cpuPct
                    }
                    $Global:PrevCpuTime[$key] = $proc.TotalProcessorTime
                    $Global:PrevCpuDate[$key] = Get-Date
                }
            } catch { $cpuCtrl.Text = "~" }

            if ($Global:StartTimes[$key]) {
                $elapsed = (Get-Date) - $Global:StartTimes[$key]
                $uptimeCtrl.Text = "Uptime: {0:hh\:mm\:ss}" -f $elapsed
            }
        } else {
            $indicator.Fill = [System.Windows.Media.BrushConverter]::new().ConvertFromString("#EF4444")
            $statTxt.Text = "Stopped"
            $statTxt.Foreground = [System.Windows.Media.BrushConverter]::new().ConvertFromString("#9CA3AF")
            $cpuCtrl.Text = "-"; $ramCtrl.Text = "-"; $pidCtrl.Text = "-"; $uptimeCtrl.Text = "Uptime: -"
        }
    }
    $controls["txtItsmCpu"].Text = "$totalItsmCpu%"
    $controls["txtItsmRam"].Text = "$totalItsmRam MB"

    foreach ($key in @("fastapi","telemetry","assets","printers")) {
        $ucKey = $key.Substring(0,1).ToUpper() + $key.Substring(1)
        $logCtrl = $controls["log$ucKey"]
        $scrollCtrl = $controls["scroll$ucKey"]
        if ($logCtrl -and $Global:LogBuffers[$key].Count -gt 0) {
            $logCtrl.Text = ($Global:LogBuffers[$key] | Select-Object -Last 200) -join "`n"
            if ($scrollCtrl) { $scrollCtrl.ScrollToEnd() }
        }
    }
})
$metricsTimer.Start()

$usersTimer = [System.Windows.Threading.DispatcherTimer]::new()
$usersTimer.Interval = [TimeSpan]::FromSeconds(5)
$usersTimer.Add_Tick({
    try {
        $conns = Get-NetTCPConnection -LocalPort 8000 -State Established -ErrorAction SilentlyContinue |
            Where-Object { $_.RemoteAddress -ne "127.0.0.1" -and $_.RemoteAddress -ne "::1" } |
            Group-Object RemoteAddress

        $userList = @()
        foreach ($g in $conns) {
            # Removed slow synchronous DNS resolution to prevent UI freezing
            $userList += [PSCustomObject]@{ IP = $g.Name; Host = "--"; Count = $g.Count }
        }
        $controls["lvUsers"].ItemsSource = $userList
        $total = ($userList | Measure-Object -Property Count -Sum).Sum
        if (-not $total) { $total = 0 }
        $controls["txtUserCount"].Text = "$total Active Connections (Port 8000)"
    } catch {}
})
$usersTimer.Start()

$window.Add_Closing({
    $metricsTimer.Stop()
    $usersTimer.Stop()
    $running = @()
    foreach ($k in @("fastapi","telemetry","assets","printers")) {
        if ($Global:Services[$k] -and -not $Global:Services[$k].HasExited) { $running += $k }
    }
    if ($running.Count -gt 0) {
        $result = [System.Windows.MessageBox]::Show("Stop all running services?", "ITSM Service Manager", "YesNoCancel", "Question")
        if ($result -eq "Cancel") { $_.Cancel = $true; $metricsTimer.Start(); $usersTimer.Start(); return }
        if ($result -eq "Yes") { foreach ($k in $running) { Stop-ServiceProcess -Key $k } }
    }
    Get-EventSubscriber | Unregister-Event -ErrorAction SilentlyContinue
})

$window.ShowDialog() | Out-Null


