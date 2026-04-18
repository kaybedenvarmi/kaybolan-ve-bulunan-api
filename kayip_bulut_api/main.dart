import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:kaybolan_ve_bulunan_app/config/app_theme.dart';
import 'package:kaybolan_ve_bulunan_app/services/session_manager.dart';
import 'package:kaybolan_ve_bulunan_app/screens/auth/login_screen.dart';
import 'package:kaybolan_ve_bulunan_app/screens/home/home_screen.dart';
import 'package:kaybolan_ve_bulunan_app/screens/admin/admin_dashboard_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  await Supabase.initialize(
    url: 'https://kcqikeyytshemptxbvxz.supabase.co',
    anonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtjcWlrZXl5dHNoZW1wdHhidnh6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYyNTQzNjYsImV4cCI6MjA5MTgzMDM2Nn0.LyFRsohwV9YKT3W5BxsEhuzRsfLyxG0ppZ0H3ldPLZU',
  );

  await SessionManager().loadSession();
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    final user = SessionManager().currentUser;

    Widget home;
    if (user == null) {
      home = const LoginScreen();
    } else if (user.isAdmin) {
      home = const AdminDashboardScreen();
    } else {
      home = const HomeScreen();
    }

    return MaterialApp(
      title: 'Kayıp ve Bulunan',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.theme,
      home: home,
    );
  }
}
